"""Conflict detection for ERP synchronization."""

from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ConflictType:
    """Enumeration of conflict types."""
    CONCURRENT_UPDATE = "concurrent_update"
    DELETED_IN_SOURCE = "deleted_in_source"
    DELETED_IN_TARGET = "deleted_in_target"
    VALUE_MISMATCH = "value_mismatch"
    MISSING_DEPENDENCY = "missing_dependency"


class ConflictDetector:
    """Detects conflicts between source and target data during synchronization."""

    def __init__(self):
        """Initialize the conflict detector."""
        self.conflicts: List[Dict[str, Any]] = []

    def detect(
        self,
        source_data: List[Dict[str, Any]],
        target_data: List[Dict[str, Any]],
        key_field: str = "id"
    ) -> List[Dict[str, Any]]:
        """Detect conflicts between source and target data.
        
        Args:
            source_data: List of records from source system
            target_data: List of records from target system
            key_field: Field name to use as unique identifier
            
        Returns:
            List of detected conflicts
        """
        self.conflicts = []
        
        # Create lookup dictionaries
        source_dict = {record.get(key_field): record for record in source_data}
        target_dict = {record.get(key_field): record for record in target_data}

        # Check for conflicts in source records
        for key, source_record in source_dict.items():
            if key in target_dict:
                target_record = target_dict[key]
                self._check_record_conflicts(key, source_record, target_record)
            else:
                # Record exists in source but not in target
                self._add_conflict(
                    key,
                    ConflictType.DELETED_IN_TARGET,
                    f"Record {key} exists in source but not in target",
                    source_record,
                    None
                )

        # Check for records that exist in target but not in source
        for key, target_record in target_dict.items():
            if key not in source_dict:
                self._add_conflict(
                    key,
                    ConflictType.DELETED_IN_SOURCE,
                    f"Record {key} exists in target but not in source",
                    None,
                    target_record
                )

        logger.info(f"Detected {len(self.conflicts)} conflicts")
        return self.conflicts

    def _check_record_conflicts(
        self,
        key: Any,
        source_record: Dict[str, Any],
        target_record: Dict[str, Any]
    ) -> None:
        """Check for conflicts between a source and target record.
        
        Args:
            key: Record identifier
            source_record: Source system record
            target_record: Target system record
        """
        # Check for concurrent updates based on timestamps
        source_modified = source_record.get("modified_at") or source_record.get("updated_at")
        target_modified = target_record.get("modified_at") or target_record.get("updated_at")

        if source_modified and target_modified:
            if isinstance(source_modified, str):
                source_modified = datetime.fromisoformat(source_modified.replace('Z', '+00:00'))
            if isinstance(target_modified, str):
                target_modified = datetime.fromisoformat(target_modified.replace('Z', '+00:00'))

            # If both records were modified recently, it might be a concurrent update
            time_diff = abs((source_modified - target_modified).total_seconds())
            if time_diff < 300:  # Within 5 minutes
                if self._has_value_differences(source_record, target_record):
                    self._add_conflict(
                        key,
                        ConflictType.CONCURRENT_UPDATE,
                        f"Concurrent update detected for record {key}",
                        source_record,
                        target_record
                    )
                    return

        # Check for value mismatches
        if self._has_value_differences(source_record, target_record):
            differences = self._get_differences(source_record, target_record)
            self._add_conflict(
                key,
                ConflictType.VALUE_MISMATCH,
                f"Value mismatch in fields: {', '.join(differences.keys())}",
                source_record,
                target_record,
                differences=differences
            )

    def _has_value_differences(
        self,
        source_record: Dict[str, Any],
        target_record: Dict[str, Any],
        ignore_fields: Optional[List[str]] = None
    ) -> bool:
        """Check if two records have value differences.
        
        Args:
            source_record: Source system record
            target_record: Target system record
            ignore_fields: Fields to ignore in comparison
            
        Returns:
            True if differences exist, False otherwise
        """
        if ignore_fields is None:
            ignore_fields = ["id", "created_at", "updated_at", "modified_at"]

        for key in source_record.keys():
            if key in ignore_fields:
                continue
            if key in target_record:
                if source_record[key] != target_record[key]:
                    return True

        return False

    def _get_differences(
        self,
        source_record: Dict[str, Any],
        target_record: Dict[str, Any],
        ignore_fields: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Get detailed differences between two records.
        
        Args:
            source_record: Source system record
            target_record: Target system record
            ignore_fields: Fields to ignore in comparison
            
        Returns:
            Dictionary of differences with source and target values
        """
        if ignore_fields is None:
            ignore_fields = ["id", "created_at", "updated_at", "modified_at"]

        differences = {}
        for key in source_record.keys():
            if key in ignore_fields:
                continue
            if key in target_record:
                if source_record[key] != target_record[key]:
                    differences[key] = {
                        "source": source_record[key],
                        "target": target_record[key]
                    }

        return differences

    def _add_conflict(
        self,
        key: Any,
        conflict_type: str,
        message: str,
        source_record: Optional[Dict[str, Any]],
        target_record: Optional[Dict[str, Any]],
        differences: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> None:
        """Add a conflict to the conflicts list.
        
        Args:
            key: Record identifier
            conflict_type: Type of conflict
            message: Conflict description
            source_record: Source system record
            target_record: Target system record
            differences: Detailed field differences
        """
        conflict = {
            "key": key,
            "type": conflict_type,
            "message": message,
            "source_record": source_record,
            "target_record": target_record,
            "detected_at": datetime.utcnow().isoformat(),
        }
        
        if differences:
            conflict["differences"] = differences

        self.conflicts.append(conflict)
        logger.debug(f"Added conflict: {conflict_type} for key {key}")

    def clear_conflicts(self) -> None:
        """Clear all detected conflicts."""
        self.conflicts = []
        logger.debug("Cleared all conflicts")

    def get_conflicts_by_type(self, conflict_type: str) -> List[Dict[str, Any]]:
        """Get all conflicts of a specific type.
        
        Args:
            conflict_type: Type of conflict to filter
            
        Returns:
            List of conflicts matching the type
        """
        return [c for c in self.conflicts if c["type"] == conflict_type]

    def has_conflicts(self) -> bool:
        """Check if any conflicts were detected.
        
        Returns:
            True if conflicts exist, False otherwise
        """
        return len(self.conflicts) > 0
