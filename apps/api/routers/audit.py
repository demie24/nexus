"""
NEXUS Audit Trail Endpoints
Records and surfaces system and human-in-the-loop decisions for auditability.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.session import get_db
from database.models.models import AuditLogModel
from services.schemas import AuditLog, AuditLogCreate

router = APIRouter(prefix="/audit", tags=["Audit Logs"])


@router.get("", response_model=List[AuditLog])
def list_audit_logs(
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Retrieve immutable audit trail entries in reverse chronological order."""
    query = db.query(AuditLogModel)
    if resource_type:
        query = query.filter(AuditLogModel.resource_type == resource_type)
    logs = query.order_by(desc(AuditLogModel.timestamp)).limit(limit).all()
    return logs


@router.post("", response_model=AuditLog, status_code=status.HTTP_201_CREATED)
def record_audit_log(entry: AuditLogCreate, db: Session = Depends(get_db)):
    """Record an action into the audit trail."""
    log_data = entry.model_dump()
    log_data["provenance"] = entry.provenance.value if hasattr(entry.provenance, "value") else str(entry.provenance)

    record = AuditLogModel(**log_data)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
