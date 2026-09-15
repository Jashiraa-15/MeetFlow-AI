from collections import defaultdict
from typing import Dict, List, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Meeting, ActionItem
from app.auth import get_current_user

router = APIRouter(prefix="/calendar", tags=["Calendar"])

@router.get("", response_model=Dict[str, List[Dict[str, Any]]])
def get_calendar_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns action items with non-null deadlines grouped by date (YYYY-MM-DD -> list of task objects)
    for easy rendering in the frontend calendar view.
    """
    items = (
        db.query(ActionItem)
        .join(Meeting, ActionItem.meeting_id == Meeting.id)
        .filter(Meeting.user_id == current_user.id, ActionItem.deadline != None)
        .order_by(ActionItem.deadline.asc(), ActionItem.id.asc())
        .all()
    )


    calendar_dict: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in items:
        date_key = item.deadline.isoformat()
        calendar_dict[date_key].append({
            "id": item.id,
            "meeting_id": item.meeting_id,
            "task": item.task,
            "owner": item.owner,
            "priority": item.priority,
            "category": item.category,
            "status": item.status,
            "confidence": item.confidence,
            "needs_clarification": item.needs_clarification,
            "is_confirmed": item.is_confirmed,
            "deadline": date_key
        })

    return dict(calendar_dict)
