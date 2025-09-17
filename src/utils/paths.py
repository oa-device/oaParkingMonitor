"""
Centralized path management for oaParkingMonitor data storage.

This module provides a single source of truth for all data paths, supporting
the airport demo requirement to store data outside the project directory.
Implements hierarchical storage for efficient snapshot organization.
"""

from pathlib import Path
from typing import Optional, List
from datetime import datetime
import logging
import time
import json
import shutil

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
        # Legacy flat directories (for migration)
        self.legacy_json_snapshots_dir = self.snapshots_dir / "json"
        self.legacy_image_snapshots_dir = self.snapshots_dir / "images"
        self.exports_dir = self.parking_monitor_dir / "exports"


        # Create directories if they don't exist
        self._ensure_directories()

    def _ensure_directories(self):
        """Create all required directories"""
        directories = [
            self.parking_monitor_dir,
            self.database_dir,
            self.snapshots_dir,
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
        """SQLite database file path (legacy, replaced by EdgeStorage)"""
        return self.database_dir / "oaParkingMonitor.db"  # Unified naming

    def get_snapshot_dir(self, epoch: int) -> Path:
        """Get hierarchical directory path for snapshot based on epoch timestamp"""
        dt = datetime.fromtimestamp(epoch)
        return self.snapshots_dir / f"{dt.year:04d}" / f"{dt.month:02d}" / f"{dt.day:02d}" / f"{dt.hour:02d}"

    def get_json_snapshot_path(self, epoch: int) -> Path:
        """Get path for JSON snapshot file with hierarchical structure"""
        snapshot_dir = self.get_snapshot_dir(epoch)
        json_dir = snapshot_dir / "json"
        json_dir.mkdir(parents=True, exist_ok=True)
        return json_dir / f"{epoch}.json"

    def get_image_snapshot_path(self, epoch: int) -> Path:
        """Get path for image snapshot file with hierarchical structure"""
        snapshot_dir = self.get_snapshot_dir(epoch)
        image_dir = snapshot_dir / "images"
        image_dir.mkdir(parents=True, exist_ok=True)
        return image_dir / f"{epoch}.jpg"

    def get_export_path(self, filename: str) -> Path:
        """Get path for export file"""
        return self.exports_dir / filename

    def cleanup_old_snapshots(self, days_to_keep: int = 30) -> int:
        """
        Clean up snapshot files older than specified days from hierarchical structure.

        Args:
            days_to_keep: Number of days to retain snapshots

        Returns:
            Number of files deleted
        """
        cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
        deleted_count = 0

        # Clean hierarchical snapshots
        for year_dir in self.snapshots_dir.glob("????/"):
            if not year_dir.is_dir():
                continue

            for month_dir in year_dir.glob("??/"):
                if not month_dir.is_dir():
                    continue

                for day_dir in month_dir.glob("??/"):
                    if not day_dir.is_dir():
                        continue

                    for hour_dir in day_dir.glob("??/"):
                        if not hour_dir.is_dir():
                            continue

                        # Check JSON files
                        json_dir = hour_dir / "json"
                        if json_dir.exists():
                            for json_file in json_dir.glob("*.json"):
                                try:
                                    epoch = int(json_file.stem)
                                    if epoch < cutoff_time:
                                        json_file.unlink()
                                        deleted_count += 1
                                        logger.debug(f"Deleted old JSON snapshot: {json_file}")
                                except (ValueError, OSError) as e:
                                    logger.warning(f"Failed to process JSON file {json_file}: {e}")

                        # Check image files
                        image_dir = hour_dir / "images"
                        if image_dir.exists():
                            for image_file in image_dir.glob("*.jpg"):
                                try:
                                    epoch = int(image_file.stem)
                                    if epoch < cutoff_time:
                                        image_file.unlink()
                                        deleted_count += 1
                                        logger.debug(f"Deleted old image snapshot: {image_file}")
                                except (ValueError, OSError) as e:
                                    logger.warning(f"Failed to process image file {image_file}: {e}")

                        # Clean up empty directories
                        self._cleanup_empty_directories(hour_dir)

        # Also clean legacy flat structure if it exists
        deleted_count += self._cleanup_legacy_snapshots(cutoff_time)

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old snapshot files")

        return deleted_count

    def _cleanup_legacy_snapshots(self, cutoff_time: float) -> int:
        """Clean up old flat structure snapshots during migration period"""
        deleted_count = 0

        # Clean legacy JSON snapshots
        if self.legacy_json_snapshots_dir.exists():
            for json_file in self.legacy_json_snapshots_dir.glob("*.json"):
                try:
                    epoch = int(json_file.stem)
                    if epoch < cutoff_time:
                        json_file.unlink()
                        deleted_count += 1
                        logger.debug(f"Deleted old legacy JSON snapshot: {json_file}")
                except (ValueError, OSError) as e:
                    logger.warning(f"Failed to process legacy JSON file {json_file}: {e}")

        # Clean legacy image snapshots
        if self.legacy_image_snapshots_dir.exists():
            for image_file in self.legacy_image_snapshots_dir.glob("*.jpg"):
                try:
                    epoch = int(image_file.stem)
                    if epoch < cutoff_time:
                        image_file.unlink()
                        deleted_count += 1
                        logger.debug(f"Deleted old legacy image snapshot: {image_file}")
                except (ValueError, OSError) as e:
                    logger.warning(f"Failed to process legacy image file {image_file}: {e}")

        return deleted_count

    def _cleanup_empty_directories(self, start_dir: Path) -> None:
        """Recursively remove empty directories"""
        try:
            # Remove empty subdirectories first
            for subdir in start_dir.iterdir():
                if subdir.is_dir():
                    self._cleanup_empty_directories(subdir)

            # Remove directory if it's empty
            if start_dir.exists() and not any(start_dir.iterdir()):
                start_dir.rmdir()
                logger.debug(f"Removed empty directory: {start_dir}")
        except Exception as e:
            logger.warning(f"Failed to cleanup directory {start_dir}: {e}")

    def get_snapshots_in_range(self, from_epoch: int, to_epoch: int) -> list:
        """
        Get snapshot files within epoch range from hierarchical structure.

        Args:
            from_epoch: Start epoch timestamp
            to_epoch: End epoch timestamp

        Returns:
            List of dicts with epoch, json_path, image_path
        """
        snapshots = []

        # Calculate date range for efficient traversal
        from_date = datetime.fromtimestamp(from_epoch)
        to_date = datetime.fromtimestamp(to_epoch)

        # Search hierarchical structure
        for year_dir in self.snapshots_dir.glob("????/"):
            year = int(year_dir.name)
            if year < from_date.year or year > to_date.year:
                continue

            for month_dir in year_dir.glob("??/"):
                month = int(month_dir.name)
                if year == from_date.year and month < from_date.month:
                    continue
                if year == to_date.year and month > to_date.month:
                    continue

                for day_dir in month_dir.glob("??/"):
                    day = int(day_dir.name)
                    if year == from_date.year and month == from_date.month and day < from_date.day:
                        continue
                    if year == to_date.year and month == to_date.month and day > to_date.day:
                        continue

                    for hour_dir in day_dir.glob("??/"):
                        json_dir = hour_dir / "json"
                        if not json_dir.exists():
                            continue

                        for json_file in json_dir.glob("*.json"):
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

        # Also check legacy flat structure during migration period
        snapshots.extend(self._get_legacy_snapshots_in_range(from_epoch, to_epoch))

        # Sort by epoch and remove duplicates
        seen_epochs = set()
        unique_snapshots = []
        for snapshot in sorted(snapshots, key=lambda x: x["epoch"]):
            if snapshot["epoch"] not in seen_epochs:
                seen_epochs.add(snapshot["epoch"])
                unique_snapshots.append(snapshot)

        return unique_snapshots

    def _get_legacy_snapshots_in_range(self, from_epoch: int, to_epoch: int) -> List[dict]:
        """Get snapshots from legacy flat structure during migration"""
        snapshots = []

        # Find JSON files in legacy structure
        if self.legacy_json_snapshots_dir.exists():
            for json_file in self.legacy_json_snapshots_dir.glob("*.json"):
                try:
                    epoch = int(json_file.stem)
                    if from_epoch <= epoch <= to_epoch:
                        # Check if file exists in new structure (avoid duplicates)
                        new_json_path = self.get_json_snapshot_path(epoch)
                        if not new_json_path.exists():
                            # Legacy image path
                            legacy_image_path = self.legacy_image_snapshots_dir / f"{epoch}.jpg"
                            snapshots.append({
                                "epoch": epoch,
                                "json_path": json_file,
                                "image_path": legacy_image_path,
                                "has_image": legacy_image_path.exists(),
                                "legacy": True
                            })
                except ValueError:
                    logger.warning(f"Invalid legacy JSON snapshot filename: {json_file}")

        return snapshots

    def get_storage_stats(self) -> dict:
        """Get storage usage statistics for hierarchical structure"""
        # Count files in hierarchical structure (exclude legacy flat directories)
        hierarchical_json_count = 0
        hierarchical_image_count = 0

        # Only count files in the hierarchical pattern: YYYY/MM/DD/HH/json/*.json
        for json_file in self.snapshots_dir.rglob("????/??/??/??/json/*.json"):
            hierarchical_json_count += 1
        for image_file in self.snapshots_dir.rglob("????/??/??/??/images/*.jpg"):
            hierarchical_image_count += 1

        # Count legacy files
        legacy_json_count = 0
        legacy_image_count = 0
        if self.legacy_json_snapshots_dir.exists():
            legacy_json_count = len(list(self.legacy_json_snapshots_dir.glob("*.json")))
        if self.legacy_image_snapshots_dir.exists():
            legacy_image_count = len(list(self.legacy_image_snapshots_dir.glob("*.jpg")))

        stats = {
            "base_dir": str(self.base_data_dir),
            "total_json_files": hierarchical_json_count + legacy_json_count,
            "total_image_files": hierarchical_image_count + legacy_image_count,
            "hierarchical_json_files": hierarchical_json_count,
            "hierarchical_image_files": hierarchical_image_count,
            "legacy_json_files": legacy_json_count,
            "legacy_image_files": legacy_image_count,
            "database_exists": self.database_path.exists(),
            "migration_needed": legacy_json_count > 0 or legacy_image_count > 0,
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

    def migrate_legacy_snapshots(self, max_files_per_batch: int = 1000) -> dict:
        """
        Migrate legacy flat snapshot files to hierarchical structure.

        Args:
            max_files_per_batch: Maximum files to migrate in one batch

        Returns:
            Dict with migration statistics
        """
        logger.info("Starting snapshot migration from flat to hierarchical structure")

        migrated_json = 0
        migrated_images = 0
        failed_migrations = 0

        # Migrate JSON files
        if self.legacy_json_snapshots_dir.exists():
            json_files = list(self.legacy_json_snapshots_dir.glob("*.json"))
            logger.info(f"Found {len(json_files)} legacy JSON files to migrate")

            for i, json_file in enumerate(json_files[:max_files_per_batch]):
                try:
                    epoch = int(json_file.stem)
                    new_path = self.get_json_snapshot_path(epoch)

                    # Skip if already exists in new location
                    if not new_path.exists():
                        # Ensure directory exists
                        new_path.parent.mkdir(parents=True, exist_ok=True)
                        # Move file
                        shutil.move(str(json_file), str(new_path))
                        migrated_json += 1

                        if (i + 1) % 100 == 0:
                            logger.info(f"Migrated {i + 1} JSON files...")

                except (ValueError, OSError) as e:
                    logger.warning(f"Failed to migrate JSON file {json_file}: {e}")
                    failed_migrations += 1

        # Migrate image files
        if self.legacy_image_snapshots_dir.exists():
            image_files = list(self.legacy_image_snapshots_dir.glob("*.jpg"))
            logger.info(f"Found {len(image_files)} legacy image files to migrate")

            for i, image_file in enumerate(image_files[:max_files_per_batch]):
                try:
                    epoch = int(image_file.stem)
                    new_path = self.get_image_snapshot_path(epoch)

                    # Skip if already exists in new location
                    if not new_path.exists():
                        # Ensure directory exists
                        new_path.parent.mkdir(parents=True, exist_ok=True)
                        # Move file
                        shutil.move(str(image_file), str(new_path))
                        migrated_images += 1

                        if (i + 1) % 100 == 0:
                            logger.info(f"Migrated {i + 1} image files...")

                except (ValueError, OSError) as e:
                    logger.warning(f"Failed to migrate image file {image_file}: {e}")
                    failed_migrations += 1

        # Clean up empty legacy directories
        try:
            if self.legacy_json_snapshots_dir.exists() and not any(self.legacy_json_snapshots_dir.iterdir()):
                self.legacy_json_snapshots_dir.rmdir()
                logger.info("Removed empty legacy JSON directory")

            if self.legacy_image_snapshots_dir.exists() and not any(self.legacy_image_snapshots_dir.iterdir()):
                self.legacy_image_snapshots_dir.rmdir()
                logger.info("Removed empty legacy image directory")
        except Exception as e:
            logger.warning(f"Failed to clean up legacy directories: {e}")

        migration_stats = {
            "migrated_json_files": migrated_json,
            "migrated_image_files": migrated_images,
            "failed_migrations": failed_migrations,
            "total_migrated": migrated_json + migrated_images
        }

        logger.info(f"Migration completed: {migration_stats}")
        return migration_stats


# Global instance for use throughout the application
data_paths = DataPaths()

# Perform migration check on module import if data exists
try:
    if data_paths.snapshots_dir.exists():
        stats = data_paths.get_storage_stats()
        if stats.get("migration_needed", False):
            logger.info(f"Legacy snapshots detected: {stats['legacy_json_files']} JSON, {stats['legacy_image_files']} images")
except Exception as e:
    logger.warning(f"Failed to check migration status: {e}")


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


def migrate_snapshots_if_needed(max_files_per_batch: int = 1000) -> bool:
    """
    Automatically migrate legacy snapshots if needed.

    Args:
        max_files_per_batch: Maximum files to migrate in one batch

    Returns:
        True if migration was successful or not needed
    """
    try:
        stats = data_paths.get_storage_stats()

        if stats.get("migration_needed", False):
            logger.info("Legacy snapshots detected, starting migration")
            migration_result = data_paths.migrate_legacy_snapshots(max_files_per_batch)

            if migration_result["failed_migrations"] == 0:
                logger.info("Snapshot migration completed successfully")
                return True
            else:
                logger.warning(f"Snapshot migration completed with {migration_result['failed_migrations']} failures")
                return False
        else:
            logger.debug("No legacy snapshots found, migration not needed")
            return True

    except Exception as e:
        logger.error(f"Snapshot migration failed: {e}")
        return False