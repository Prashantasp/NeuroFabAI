"""Append-only audit trail for security-relevant actions."""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.audit import AuditLog

logger = logging.getLogger(__name__)


class AuditService:
    def log_action(
        self,
        db: Session,
        *,
        action: str,
        resource_type: str,
        user_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Optional[AuditLog]:
        """Record an action.

        Never raises: a failure to write the audit row must not roll back or fail
        the user-facing operation that succeeded. Failures are logged so the gap
        is visible.
        """
        try:
            entry = AuditLog(
                user_id=user_id,
                workspace_id=workspace_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                ip_address=(ip_address or None),
                user_agent=(user_agent or "")[:255] or None,
                request_id=request_id,
            )
            db.add(entry)
            db.commit()
            return entry
        except Exception:  # noqa: BLE001
            logger.exception("Failed to write audit log for action %s", action)
            db.rollback()
            return None


audit_service = AuditService()
