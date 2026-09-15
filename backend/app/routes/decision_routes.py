from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Meeting, Decision
from app.schemas import DecisionResponse
from app.auth import get_current_user

router = APIRouter(prefix="/decisions", tags=["Decisions"])

@router.get("", response_model=List[DecisionResponse])
def list_decisions(
    meeting_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists decisions across meetings belonging to the authenticated user.
    Optionally filters by meeting_id (returning 404 if meeting does not exist or belong to user).
    """
    if meeting_id is not None:
        meeting = (
            db.query(Meeting)
            .filter(Meeting.id == meeting_id, Meeting.user_id == current_user.id)
            .first()
        )
        if not meeting:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Meeting #{meeting_id} not found or access denied"
            )

    query = (
        db.query(Decision)
        .join(Meeting, Decision.meeting_id == Meeting.id)
        .filter(Meeting.user_id == current_user.id)
    )

    if meeting_id is not None:
        query = query.filter(Decision.meeting_id == meeting_id)

    return query.order_by(Decision.created_at.desc()).all()

