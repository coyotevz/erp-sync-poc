"""SyncLog model for tracking synchronization history."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Enum
import enum

from .base import Base


class SyncStatus(enum.Enum):
    """Enumeration of sync statuses."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    CONFLICT = "conflict"


class SyncLog(Base):
    """Model for tracking synchronization history."""

    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True)
    sync_config_id = Column(Integer, nullable=False)
    status = Column(Enum(SyncStatus), nullable=False, default=SyncStatus.PENDING)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    records_synced = Column(Integer, default=0)
    records_failed = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    details = Column(Text, nullable=True)

    def __repr__(self):
        return (
            f"<SyncLog(id={self.id}, "
            f"config_id={self.sync_config_id}, "
            f"status={self.status.value}, "
            f"started_at={self.started_at})>"
        )
