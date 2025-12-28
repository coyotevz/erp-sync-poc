"""Sync Manager for orchestrating ERP synchronization."""

from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from sqlalchemy.orm import Session

from ..models import SyncConfig, ERPSystem
from .base_sync import BaseSync
from .conflict_detector import ConflictDetector
from .sync_monitor import SyncMonitor

logger = logging.getLogger(__name__)


class SyncManager:
    """Manages synchronization operations between ERP systems."""

    def __init__(self, db_session: Session):
        """Initialize the sync manager.
        
        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session
        self.conflict_detector = ConflictDetector()
        self.monitor = SyncMonitor()
        self._sync_instances: Dict[int, BaseSync] = {}

    def register_sync_instance(self, config_id: int, sync_instance: BaseSync) -> None:
        """Register a sync instance for a configuration.
        
        Args:
            config_id: Configuration ID
            sync_instance: Sync instance to register
        """
        self._sync_instances[config_id] = sync_instance
        logger.info(f"Registered sync instance for config {config_id}")

    def get_sync_instance(self, config_id: int) -> Optional[BaseSync]:
        """Get a registered sync instance.
        
        Args:
            config_id: Configuration ID
            
        Returns:
            BaseSync instance or None if not found
        """
        return self._sync_instances.get(config_id)

    def sync_config(self, config_id: int, dry_run: bool = False) -> Dict[str, Any]:
        """Execute synchronization for a specific configuration.
        
        Args:
            config_id: Configuration ID to sync
            dry_run: If True, simulate sync without making changes
            
        Returns:
            Dictionary with sync results
        """
        config = self.db.query(SyncConfig).filter_by(id=config_id).first()
        if not config:
            raise ValueError(f"SyncConfig with id {config_id} not found")

        if not config.enabled:
            logger.warning(f"SyncConfig {config_id} is disabled")
            return {
                "status": "skipped",
                "reason": "Configuration is disabled"
            }

        logger.info(f"Starting sync for config {config_id} (dry_run={dry_run})")
        
        # Get the sync instance
        sync_instance = self.get_sync_instance(config_id)
        if not sync_instance:
            raise ValueError(f"No sync instance registered for config {config_id}")

        # Start monitoring
        self.monitor.start_sync(config_id)

        try:
            # Execute the sync
            result = sync_instance.sync(dry_run=dry_run)
            
            # Update monitoring
            self.monitor.complete_sync(
                config_id,
                success=True,
                records_synced=result.get("synced", 0),
                records_failed=result.get("failed", 0)
            )
            
            logger.info(f"Sync completed for config {config_id}: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Sync failed for config {config_id}: {e}", exc_info=True)
            self.monitor.complete_sync(
                config_id,
                success=False,
                error_message=str(e)
            )
            raise

    def sync_all_active(self, dry_run: bool = False) -> List[Dict[str, Any]]:
        """Execute synchronization for all active configurations.
        
        Args:
            dry_run: If True, simulate sync without making changes
            
        Returns:
            List of sync results for each configuration
        """
        active_configs = self.db.query(SyncConfig).filter_by(enabled=True).all()
        results = []

        for config in active_configs:
            try:
                result = self.sync_config(config.id, dry_run=dry_run)
                results.append({
                    "config_id": config.id,
                    "config_name": config.name,
                    "result": result
                })
            except Exception as e:
                logger.error(f"Failed to sync config {config.id}: {e}")
                results.append({
                    "config_id": config.id,
                    "config_name": config.name,
                    "result": {
                        "status": "error",
                        "error": str(e)
                    }
                })

        return results

    def detect_conflicts(self, config_id: int) -> List[Dict[str, Any]]:
        """Detect conflicts for a specific configuration.
        
        Args:
            config_id: Configuration ID
            
        Returns:
            List of detected conflicts
        """
        sync_instance = self.get_sync_instance(config_id)
        if not sync_instance:
            raise ValueError(f"No sync instance registered for config {config_id}")

        # Get data from both systems
        source_data = sync_instance.fetch_source_data()
        target_data = sync_instance.fetch_target_data()

        # Detect conflicts
        conflicts = self.conflict_detector.detect(source_data, target_data)
        
        logger.info(f"Detected {len(conflicts)} conflicts for config {config_id}")
        return conflicts

    def get_sync_status(self, config_id: int) -> Dict[str, Any]:
        """Get current sync status for a configuration.
        
        Args:
            config_id: Configuration ID
            
        Returns:
            Dictionary with current status information
        """
        return self.monitor.get_status(config_id)

    def get_all_statuses(self) -> Dict[int, Dict[str, Any]]:
        """Get sync status for all configurations.
        
        Returns:
            Dictionary mapping config IDs to their status
        """
        return self.monitor.get_all_statuses()
