"""Sync monitoring and metrics tracking."""

from typing import Dict, Any, Optional
from datetime import datetime
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class SyncMonitor:
    """Monitors synchronization operations and tracks metrics."""

    def __init__(self):
        """Initialize the sync monitor."""
        self._sync_status: Dict[int, Dict[str, Any]] = {}
        self._metrics: Dict[int, Dict[str, Any]] = defaultdict(lambda: {
            "total_syncs": 0,
            "successful_syncs": 0,
            "failed_syncs": 0,
            "total_records_synced": 0,
            "total_records_failed": 0,
            "last_sync_at": None,
            "average_duration": 0.0,
        })

    def start_sync(self, config_id: int) -> None:
        """Mark the start of a sync operation.
        
        Args:
            config_id: Configuration ID
        """
        self._sync_status[config_id] = {
            "status": "in_progress",
            "started_at": datetime.utcnow(),
            "completed_at": None,
            "records_synced": 0,
            "records_failed": 0,
            "error_message": None,
        }
        logger.info(f"Started sync monitoring for config {config_id}")

    def complete_sync(
        self,
        config_id: int,
        success: bool = True,
        records_synced: int = 0,
        records_failed: int = 0,
        error_message: Optional[str] = None
    ) -> None:
        """Mark the completion of a sync operation.
        
        Args:
            config_id: Configuration ID
            success: Whether the sync was successful
            records_synced: Number of records successfully synced
            records_failed: Number of records that failed to sync
            error_message: Error message if sync failed
        """
        if config_id not in self._sync_status:
            logger.warning(f"No sync in progress for config {config_id}")
            return

        completed_at = datetime.utcnow()
        started_at = self._sync_status[config_id]["started_at"]
        duration = (completed_at - started_at).total_seconds()

        self._sync_status[config_id].update({
            "status": "success" if success else "failed",
            "completed_at": completed_at,
            "records_synced": records_synced,
            "records_failed": records_failed,
            "error_message": error_message,
            "duration": duration,
        })

        # Update metrics
        metrics = self._metrics[config_id]
        metrics["total_syncs"] += 1
        if success:
            metrics["successful_syncs"] += 1
        else:
            metrics["failed_syncs"] += 1
        
        metrics["total_records_synced"] += records_synced
        metrics["total_records_failed"] += records_failed
        metrics["last_sync_at"] = completed_at

        # Update average duration
        total_syncs = metrics["total_syncs"]
        current_avg = metrics["average_duration"]
        metrics["average_duration"] = (
            (current_avg * (total_syncs - 1) + duration) / total_syncs
        )

        logger.info(
            f"Completed sync for config {config_id}: "
            f"success={success}, duration={duration:.2f}s, "
            f"synced={records_synced}, failed={records_failed}"
        )

    def get_status(self, config_id: int) -> Dict[str, Any]:
        """Get the current status of a sync operation.
        
        Args:
            config_id: Configuration ID
            
        Returns:
            Dictionary with current status
        """
        if config_id not in self._sync_status:
            return {
                "status": "idle",
                "message": "No sync operation recorded"
            }
        
        return self._sync_status[config_id].copy()

    def get_metrics(self, config_id: int) -> Dict[str, Any]:
        """Get metrics for a specific configuration.
        
        Args:
            config_id: Configuration ID
            
        Returns:
            Dictionary with metrics
        """
        return self._metrics[config_id].copy()

    def get_all_statuses(self) -> Dict[int, Dict[str, Any]]:
        """Get status for all configurations.
        
        Returns:
            Dictionary mapping config IDs to their status
        """
        return {config_id: status.copy() for config_id, status in self._sync_status.items()}

    def get_all_metrics(self) -> Dict[int, Dict[str, Any]]:
        """Get metrics for all configurations.
        
        Returns:
            Dictionary mapping config IDs to their metrics
        """
        return {config_id: metrics.copy() for config_id, metrics in self._metrics.items()}

    def is_sync_in_progress(self, config_id: int) -> bool:
        """Check if a sync is currently in progress.
        
        Args:
            config_id: Configuration ID
            
        Returns:
            True if sync is in progress, False otherwise
        """
        if config_id not in self._sync_status:
            return False
        
        return self._sync_status[config_id]["status"] == "in_progress"

    def get_success_rate(self, config_id: int) -> float:
        """Calculate the success rate for a configuration.
        
        Args:
            config_id: Configuration ID
            
        Returns:
            Success rate as a percentage (0-100)
        """
        metrics = self._metrics[config_id]
        total = metrics["total_syncs"]
        
        if total == 0:
            return 0.0
        
        return (metrics["successful_syncs"] / total) * 100

    def clear_status(self, config_id: int) -> None:
        """Clear the status for a specific configuration.
        
        Args:
            config_id: Configuration ID
        """
        if config_id in self._sync_status:
            del self._sync_status[config_id]
            logger.debug(f"Cleared status for config {config_id}")

    def clear_metrics(self, config_id: int) -> None:
        """Clear the metrics for a specific configuration.
        
        Args:
            config_id: Configuration ID
        """
        if config_id in self._metrics:
            del self._metrics[config_id]
            logger.debug(f"Cleared metrics for config {config_id}")

    def reset(self) -> None:
        """Reset all status and metrics."""
        self._sync_status.clear()
        self._metrics.clear()
        logger.info("Reset all sync monitoring data")
