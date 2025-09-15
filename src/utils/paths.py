"""
Centralized path management for oaParkingMonitor data storage.

This module provides a single source of truth for all data paths, supporting
the airport demo requirement to store data outside the project directory.
"""

import os
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class DataPaths:
    """Centralized path management for oaParkingMonitor data storage"""
    
    def __init__(self, base_data_dir: Optional[str] = None):
        """
        Initialize data paths.
        
        Args:
            base_data_dir: Override default base directory (for testing)
        """
        if base_data_dir:
            self.base_data_dir = Path(base_data_dir)
        else:
            # Default: ~/orangead/data/ (outside project directory)
            self.base_data_dir = Path.home() / "orangead" / "data"
        
        # Core directory structure
        self.parking_monitor_dir = self.base_data_dir / "oaParkingMonitor"  # Unified naming
        self.database_dir = self.parking_monitor_dir / "database"
        self.snapshots_dir = self.parking_monitor_dir / "snapshots"
        self.json_snapshots_dir = self.snapshots_dir / "json"
        self.image_snapshots_dir = self.snapshots_dir / "images"
        self.exports_dir = self.parking_monitor_dir / "exports"
        
        # Legacy paths for backward compatibility
        self.legacy_project_data_dir = Path.home() / "orangead" / "oaParkingMonitor" / "data"
        
        # Create directories if they don't exist
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Create all required directories"""
        directories = [
            self.parking_monitor_dir,
            self.database_dir,
            self.snapshots_dir,
            self.json_snapshots_dir,
            self.image_snapshots_dir,
            self.exports_dir
        ]
        
        for directory in directories:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Ensured directory exists: {directory}")
            except Exception as e:
                logger.error(f"Failed to create directory {directory}: {e}")
                raise
    
    @property
    def database_path(self) -> Path:
        """SQLite database file path"""
        return self.database_dir / "oaParkingMonitor.db"  # Unified naming
    
    @property
    def legacy_database_path(self) -> Path:
        """Legacy database path for migration"""
        return self.legacy_project_data_dir / "oaParkingMonitor.db"  # Unified naming
    
    def get_json_snapshot_path(self, epoch: int) -> Path:
        """Get path for JSON snapshot file"""
        return self.json_snapshots_dir / f"{epoch}.json"
    
    def get_image_snapshot_path(self, epoch: int) -> Path:
        """Get path for image snapshot file"""
        return self.image_snapshots_dir / f"{epoch}.jpg"
    
    def get_export_path(self, filename: str) -> Path:
        """Get path for export file"""
        return self.exports_dir / filename
    
    def migrate_legacy_database(self) -> bool:
        """
        Migrate database from legacy location to new location.
        
        Returns:
            True if migration was successful or not needed
        """
        if not self.legacy_database_path.exists():
            logger.info("No legacy database found, skipping migration")
            return True
        
        if self.database_path.exists():
            logger.info(f"Database already exists at {self.database_path}, skipping migration")
            return True
        
        try:
            import shutil
            logger.info(f"Migrating database from {self.legacy_database_path} to {self.database_path}")
            shutil.copy2(self.legacy_database_path, self.database_path)
            logger.info("Database migration completed successfully")
            return True
        except Exception as e:
            logger.error(f"Database migration failed: {e}")
            return False
    
    def cleanup_old_snapshots(self, days_to_keep: int = 30) -> int:
        """
        Clean up snapshot files older than specified days.
        
        Args:
            days_to_keep: Number of days to retain snapshots
            
        Returns:
            Number of files deleted
        """
        import time
        
        cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
        deleted_count = 0
        
        # Clean JSON snapshots
        for json_file in self.json_snapshots_dir.glob("*.json"):
            try:
                epoch = int(json_file.stem)
                if epoch < cutoff_time:
                    json_file.unlink()
                    deleted_count += 1
                    logger.debug(f"Deleted old JSON snapshot: {json_file}")
            except (ValueError, OSError) as e:
                logger.warning(f"Failed to process JSON file {json_file}: {e}")
        
        # Clean image snapshots
        for image_file in self.image_snapshots_dir.glob("*.jpg"):
            try:
                epoch = int(image_file.stem)
                if epoch < cutoff_time:
                    image_file.unlink()
                    deleted_count += 1
                    logger.debug(f"Deleted old image snapshot: {image_file}")
            except (ValueError, OSError) as e:
                logger.warning(f"Failed to process image file {image_file}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old snapshot files")
        
        return deleted_count
    
    def get_snapshots_in_range(self, from_epoch: int, to_epoch: int) -> list:
        """
        Get snapshot files within epoch range.
        
        Args:
            from_epoch: Start epoch timestamp
            to_epoch: End epoch timestamp
            
        Returns:
            List of dicts with epoch, json_path, image_path
        """
        snapshots = []
        
        # Find JSON files in range
        for json_file in self.json_snapshots_dir.glob("*.json"):
            try:
                epoch = int(json_file.stem)
                if from_epoch <= epoch <= to_epoch:
                    image_path = self.get_image_snapshot_path(epoch)
                    snapshots.append({
                        "epoch": epoch,
                        "json_path": json_file,
                        "image_path": image_path,
                        "has_image": image_path.exists()
                    })
            except ValueError:
                logger.warning(f"Invalid JSON snapshot filename: {json_file}")
        
        # Sort by epoch
        snapshots.sort(key=lambda x: x["epoch"])
        return snapshots
    
    def get_storage_stats(self) -> dict:
        """Get storage usage statistics"""
        stats = {
            "base_dir": str(self.base_data_dir),
            "total_json_files": len(list(self.json_snapshots_dir.glob("*.json"))),
            "total_image_files": len(list(self.image_snapshots_dir.glob("*.jpg"))),
            "database_exists": self.database_path.exists(),
            "legacy_database_exists": self.legacy_database_path.exists()
        }
        
        # Calculate directory sizes
        try:
            def get_dir_size(path: Path) -> int:
                return sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
            
            stats["database_size_mb"] = get_dir_size(self.database_dir) / (1024 * 1024)
            stats["snapshots_size_mb"] = get_dir_size(self.snapshots_dir) / (1024 * 1024)
            stats["total_size_mb"] = get_dir_size(self.parking_monitor_dir) / (1024 * 1024)
        except Exception as e:
            logger.warning(f"Failed to calculate directory sizes: {e}")
            stats["size_calculation_error"] = str(e)
        
        return stats


# Global instance for use throughout the application
data_paths = DataPaths()


def get_data_paths() -> DataPaths:
    """Get the global data paths instance"""
    return data_paths


def initialize_data_paths(base_dir: Optional[str] = None) -> DataPaths:
    """
    Initialize data paths with optional custom base directory.
    
    Args:
        base_dir: Custom base directory (for testing)
        
    Returns:
        DataPaths instance
    """
    global data_paths
    data_paths = DataPaths(base_dir)
    return data_paths


# Convenience functions for common operations
def get_database_url() -> str:
    """Get SQLite database URL for SQLAlchemy"""
    db_path = data_paths.database_path
    return f"sqlite+aiosqlite:///{db_path}"


def save_snapshot_json(epoch: int, data: dict) -> bool:
    """
    Save snapshot data as JSON file.
    
    Args:
        epoch: Epoch timestamp
        data: Snapshot data to save
        
    Returns:
        True if successful
    """
    import json
    
    try:
        json_path = data_paths.get_json_snapshot_path(epoch)
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        logger.debug(f"Saved JSON snapshot: {json_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to save JSON snapshot {epoch}: {e}")
        return False


def save_snapshot_image(epoch: int, image_bytes: bytes) -> bool:
    """
    Save snapshot image as JPEG file.
    
    Args:
        epoch: Epoch timestamp
        image_bytes: JPEG image data
        
    Returns:
        True if successful
    """
    try:
        image_path = data_paths.get_image_snapshot_path(epoch)
        with open(image_path, 'wb') as f:
            f.write(image_bytes)
        logger.debug(f"Saved image snapshot: {image_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to save image snapshot {epoch}: {e}")
        return False


def load_snapshot_json(epoch: int) -> Optional[dict]:
    """
    Load snapshot JSON data.
    
    Args:
        epoch: Epoch timestamp
        
    Returns:
        Snapshot data dict or None if not found
    """
    import json
    
    try:
        json_path = data_paths.get_json_snapshot_path(epoch)
        if not json_path.exists():
            return None
        
        with open(json_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load JSON snapshot {epoch}: {e}")
        return None


def load_snapshot_image(epoch: int) -> Optional[bytes]:
    """
    Load snapshot image data.
    
    Args:
        epoch: Epoch timestamp
        
    Returns:
        Image bytes or None if not found
    """
    try:
        image_path = data_paths.get_image_snapshot_path(epoch)
        if not image_path.exists():
            return None
        
        with open(image_path, 'rb') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to load image snapshot {epoch}: {e}")
        return None