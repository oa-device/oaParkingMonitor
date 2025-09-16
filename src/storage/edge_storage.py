"""
Edge device storage implementation
Append-only JSON files with SQLite index for fast timestamp queries
"""

import os
import json
import time
import sqlite3
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from ..models.edge import Detection


class EdgeStorage:
    """
    Resilient local storage for edge device
    - Append-only JSON files (one per detection)
    - SQLite index for fast timestamp queries
    - 30-day retention with automatic cleanup
    - Survives power loss and network outages
    """

    def __init__(self, base_path: Optional[str] = None):
        """
        Initialize edge storage

        Args:
            base_path: Base storage directory (default: ~/orangead/data/oaParkingMonitor)
        """
        self.logger = logging.getLogger(__name__)

        # Storage paths
        if base_path:
            self.base_path = Path(base_path)
        else:
            self.base_path = Path.home() / "orangead" / "data" / "oaParkingMonitor"

        self.detections_path = self.base_path / "detections"
        self.index_path = self.base_path / "index.db"
        self.config_path = self.base_path / "config.yaml"
        self.snapshots_path = self.base_path / "snapshots"

        # Ensure directories exist
        self._ensure_directories()

        # Initialize SQLite index
        self._init_index()

        # Background cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None

    def _ensure_directories(self):
        """Create directory structure if it doesn't exist"""
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.detections_path.mkdir(exist_ok=True)
        self.snapshots_path.mkdir(exist_ok=True)

        # Create year/month/day structure
        now = datetime.now()
        year_path = self.detections_path / str(now.year)
        month_path = year_path / f"{now.month:02d}"
        day_path = month_path / f"{now.day:02d}"
        day_path.mkdir(parents=True, exist_ok=True)

    def _init_index(self):
        """Initialize SQLite index for fast timestamp queries"""
        try:
            with sqlite3.connect(str(self.index_path)) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS detections (
                        id TEXT PRIMARY KEY,
                        ts INTEGER NOT NULL,
                        file_path TEXT NOT NULL,
                        uploaded BOOLEAN DEFAULT FALSE,
                        created_at INTEGER DEFAULT (strftime('%s', 'now') * 1000)
                    )
                """)

                # Index for timestamp queries
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_ts ON detections(ts)
                """)

                # Index for upload status queries
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_uploaded ON detections(uploaded)
                """)

                # Index for cleanup queries
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_created_at ON detections(created_at)
                """)

                conn.commit()

            self.logger.info("SQLite index initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize SQLite index: {e}")
            raise

    def _get_detection_file_path(self, detection: Detection) -> Path:
        """
        Get file path for detection based on timestamp
        Format: detections/YYYY/MM/DD/timestamp.json
        """
        dt = datetime.fromtimestamp(detection.ts / 1000.0)
        file_path = (
            self.detections_path /
            str(dt.year) /
            f"{dt.month:02d}" /
            f"{dt.day:02d}" /
            f"{detection.ts}.json"
        )

        # Ensure directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        return file_path

    async def store_detection(self, detection: Detection) -> bool:
        """
        Store detection in append-only file and update index

        Args:
            detection: Detection data to store

        Returns:
            Success status
        """
        try:
            # Get file path
            file_path = self._get_detection_file_path(detection)

            # Write detection to JSON file
            detection_data = detection.model_dump()
            with open(file_path, 'w') as f:
                json.dump(detection_data, f, indent=2)

            # Update SQLite index
            relative_path = str(file_path.relative_to(self.base_path))
            with sqlite3.connect(str(self.index_path)) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO detections (id, ts, file_path, uploaded)
                    VALUES (?, ?, ?, ?)
                """, (detection.id, detection.ts, relative_path, detection.uploaded))
                conn.commit()

            self.logger.debug(f"Stored detection {detection.id} at {file_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to store detection {detection.id}: {e}")
            return False

    async def get_detections(self,
                           from_ts: Optional[int] = None,
                           to_ts: Optional[int] = None,
                           limit: int = 100,
                           uploaded_only: Optional[bool] = None,
                           sort_order: str = "desc") -> List[Detection]:
        """
        Retrieve detections based on timestamp range with professional defaults

        Args:
            from_ts: Start timestamp (inclusive, milliseconds since epoch)
            to_ts: End timestamp (inclusive, milliseconds since epoch)
            limit: Maximum number of detections to return (default: 100, max: 10000)
            uploaded_only: Filter by upload status
            sort_order: Sort order - 'asc' or 'desc' (default: 'desc' - newest first)

        Returns:
            List of detections

        Raises:
            ValueError: If parameters are invalid
        """
        try:
            # Validate parameters
            if limit > 10000:
                raise ValueError("Limit cannot exceed 10000")
            
            if from_ts is not None and to_ts is not None and from_ts > to_ts:
                raise ValueError("from_ts cannot be greater than to_ts")
            
            # Validate time range (max 7 days = 604800000 ms)
            if from_ts is not None and to_ts is not None:
                time_range = to_ts - from_ts
                if time_range > 604800000:  # 7 days in milliseconds
                    raise ValueError("Time range cannot exceed 7 days")
            
            # Validate sort order
            if sort_order not in ["asc", "desc"]:
                raise ValueError("sort_order must be 'asc' or 'desc'")

            # Build query
            conditions = []
            params = []

            if from_ts is not None:
                conditions.append("ts >= ?")
                params.append(from_ts)

            if to_ts is not None:
                conditions.append("ts <= ?")
                params.append(to_ts)

            if uploaded_only is not None:
                conditions.append("uploaded = ?")
                params.append(uploaded_only)

            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            order_clause = f"ORDER BY ts {sort_order.upper()}"
            params.append(limit)

            # Query index
            with sqlite3.connect(str(self.index_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(f"""
                    SELECT id, ts, file_path, uploaded
                    FROM detections
                    {where_clause}
                    {order_clause}
                    LIMIT ?
                """, params)

                rows = cursor.fetchall()

            # Load detections from files
            detections = []
            for row in rows:
                try:
                    file_path = self.base_path / row['file_path']
                    if file_path.exists():
                        with open(file_path, 'r') as f:
                            data = json.load(f)
                        detections.append(Detection(**data))
                    else:
                        self.logger.warning(f"Detection file not found: {file_path}")

                except Exception as e:
                    self.logger.error(f"Failed to load detection {row['id']}: {e}")
                    continue

            self.logger.debug(f"Retrieved {len(detections)} detections")
            return detections

        except Exception as e:
            self.logger.error(f"Failed to get detections: {e}")
            return []

    async def get_unuploaded_detections(self, limit: int = 100) -> List[Detection]:
        """Get detections that haven't been uploaded yet"""
        return await self.get_detections(uploaded_only=False, limit=limit)

    async def mark_as_uploaded(self, detection_ids: List[str]) -> bool:
        """
        Mark detections as uploaded

        Args:
            detection_ids: List of detection IDs to mark as uploaded

        Returns:
            Success status
        """
        try:
            with sqlite3.connect(str(self.index_path)) as conn:
                placeholders = ','.join(['?' for _ in detection_ids])
                conn.execute(f"""
                    UPDATE detections
                    SET uploaded = TRUE
                    WHERE id IN ({placeholders})
                """, detection_ids)
                conn.commit()

                # Also update the JSON files
                for detection_id in detection_ids:
                    cursor = conn.execute("""
                        SELECT file_path FROM detections WHERE id = ?
                    """, (detection_id,))
                    row = cursor.fetchone()

                    if row:
                        file_path = self.base_path / row[0]
                        if file_path.exists():
                            with open(file_path, 'r') as f:
                                data = json.load(f)
                            data['uploaded'] = True
                            with open(file_path, 'w') as f:
                                json.dump(data, f, indent=2)

            self.logger.info(f"Marked {len(detection_ids)} detections as uploaded")
            return True

        except Exception as e:
            self.logger.error(f"Failed to mark detections as uploaded: {e}")
            return False

    async def cleanup_old_detections(self, retention_days: int = 30) -> int:
        """
        Clean up detections older than retention period

        Args:
            retention_days: Number of days to retain data

        Returns:
            Number of detections cleaned up
        """
        try:
            cutoff_time = int((time.time() - retention_days * 24 * 3600) * 1000)

            # Get old detections
            with sqlite3.connect(str(self.index_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT id, file_path FROM detections WHERE created_at < ?
                """, (cutoff_time,))
                old_detections = cursor.fetchall()

                # Delete files
                deleted_count = 0
                for row in old_detections:
                    try:
                        file_path = self.base_path / row['file_path']
                        if file_path.exists():
                            file_path.unlink()
                            deleted_count += 1
                    except Exception as e:
                        self.logger.warning(f"Failed to delete file {row['file_path']}: {e}")

                # Remove from index
                conn.execute("DELETE FROM detections WHERE created_at < ?", (cutoff_time,))
                conn.commit()

                # Vacuum to reclaim space
                conn.execute("VACUUM")

            self.logger.info(f"Cleaned up {deleted_count} old detections")
            return deleted_count

        except Exception as e:
            self.logger.error(f"Failed to cleanup old detections: {e}")
            return 0

    async def get_detections_by_ids(self, detection_ids: List[str]) -> List[Detection]:
        """
        Retrieve detections by specific IDs (supports comma-separated queries from cloud)

        Args:
            detection_ids: List of detection IDs to retrieve

        Returns:
            List of detections matching the IDs
        """
        try:
            if not detection_ids:
                return []

            # Query index for specified IDs
            with sqlite3.connect(str(self.index_path)) as conn:
                conn.row_factory = sqlite3.Row
                placeholders = ','.join(['?' for _ in detection_ids])
                cursor = conn.execute(f"""
                    SELECT id, ts, file_path, uploaded
                    FROM detections
                    WHERE id IN ({placeholders})
                    ORDER BY ts DESC
                """, detection_ids)

                rows = cursor.fetchall()

            # Load detections from files
            detections = []
            for row in rows:
                try:
                    file_path = self.base_path / row['file_path']
                    if file_path.exists():
                        with open(file_path, 'r') as f:
                            data = json.load(f)
                        detections.append(Detection(**data))
                    else:
                        self.logger.warning(f"Detection file not found: {file_path}")

                except Exception as e:
                    self.logger.error(f"Failed to load detection {row['id']}: {e}")
                    continue

            return detections

        except Exception as e:
            self.logger.error(f"Failed to get detections by IDs: {e}")
            return []

    async def get_detections_enhanced(self,
                                    from_ts: Optional[int] = None,
                                    to_ts: Optional[int] = None,
                                    limit: int = 100,
                                    uploaded: Optional[bool] = None,
                                    detection_ids: Optional[List[str]] = None,
                                    camera_ids: Optional[List[str]] = None,
                                    site_ids: Optional[List[str]] = None,
                                    zone_ids: Optional[List[str]] = None,
                                    sort_order: str = "desc") -> List[Detection]:
        """
        Enhanced detection retrieval with multiple filtering options for cloud polling

        Args:
            from_ts: Start timestamp (inclusive, milliseconds since epoch)
            to_ts: End timestamp (inclusive, milliseconds since epoch)
            limit: Maximum number of detections to return
            uploaded: Filter by upload status (True/False/None for all)
            detection_ids: List of specific detection IDs to retrieve
            camera_ids: List of camera IDs to filter by
            site_ids: List of site IDs to filter by
            zone_ids: List of zone IDs to filter by
            sort_order: Sort order - 'asc' or 'desc'

        Returns:
            List of detections matching all criteria
        """
        try:
            # If specific IDs requested, use direct ID query
            if detection_ids:
                return await self.get_detections_by_ids(detection_ids)

            # Validate parameters
            if limit > 10000:
                raise ValueError("Limit cannot exceed 10000")

            if from_ts is not None and to_ts is not None and from_ts > to_ts:
                raise ValueError("from_ts cannot be greater than to_ts")

            if sort_order not in ["asc", "desc"]:
                raise ValueError("sort_order must be 'asc' or 'desc'")

            # Build query conditions
            conditions = []
            params = []

            # Timestamp filtering
            if from_ts is not None:
                conditions.append("ts >= ?")
                params.append(from_ts)

            if to_ts is not None:
                conditions.append("ts <= ?")
                params.append(to_ts)

            # Upload status filtering
            if uploaded is not None:
                conditions.append("uploaded = ?")
                params.append(uploaded)

            # Build WHERE clause
            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            order_clause = f"ORDER BY ts {sort_order.upper()}"
            params.append(limit)

            # Query index
            with sqlite3.connect(str(self.index_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(f"""
                    SELECT id, ts, file_path, uploaded
                    FROM detections
                    {where_clause}
                    {order_clause}
                    LIMIT ?
                """, params)

                rows = cursor.fetchall()

            # Load detections from files
            detections = []
            for row in rows:
                try:
                    file_path = self.base_path / row['file_path']
                    if file_path.exists():
                        with open(file_path, 'r') as f:
                            data = json.load(f)

                        detection = Detection(**data)

                        # Apply filtering on detection data (not indexed in SQLite)
                        if camera_ids and detection.cameraId not in camera_ids:
                            continue
                        if site_ids and detection.siteId not in site_ids:
                            continue
                        if zone_ids and detection.zoneId not in zone_ids:
                            continue

                        detections.append(detection)

                    else:
                        self.logger.warning(f"Detection file not found: {file_path}")

                except Exception as e:
                    self.logger.error(f"Failed to load detection {row['id']}: {e}")
                    continue

            return detections

        except ValueError as e:
            # Re-raise validation errors
            raise
        except Exception as e:
            self.logger.error(f"Failed to get enhanced detections: {e}")
            return []

    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        try:
            with sqlite3.connect(str(self.index_path)) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM detections")
                total_detections = cursor.fetchone()[0]

                cursor = conn.execute("SELECT COUNT(*) FROM detections WHERE uploaded = FALSE")
                unuploaded_detections = cursor.fetchone()[0]

                cursor = conn.execute("SELECT MIN(ts), MAX(ts) FROM detections")
                row = cursor.fetchone()
                oldest_ts, newest_ts = row if row[0] else (None, None)

            # Calculate directory size
            total_size = sum(f.stat().st_size for f in self.base_path.rglob('*') if f.is_file())

            return {
                'total_detections': total_detections,
                'unuploaded_detections': unuploaded_detections,
                'oldest_detection_ts': oldest_ts,
                'newest_detection_ts': newest_ts,
                'storage_size_bytes': total_size,
                'storage_path': str(self.base_path)
            }

        except Exception as e:
            self.logger.error(f"Failed to get storage stats: {e}")
            return {}

    async def start_cleanup_task(self):
        """Start background cleanup task"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop_cleanup_task(self):
        """Stop background cleanup task"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    async def _cleanup_loop(self):
        """Background cleanup loop - runs every 24 hours"""
        while True:
            try:
                await asyncio.sleep(24 * 3600)  # 24 hours
                await self.cleanup_old_detections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")