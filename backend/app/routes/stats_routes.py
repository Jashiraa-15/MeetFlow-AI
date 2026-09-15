from datetime import date
from collections import defaultdict
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Meeting, ActionItem, ItemStatus
from app.schemas import StatsResponse, OwnerWorkload
from app.auth import get_current_user

router = APIRouter(prefix="/stats", tags=["Statistics"])

@router.get("", response_model=StatsResponse)
def get_user_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Calculates summary stats for the authenticated user:
    - total meetings
    - total action items
    - percentage needing clarification
    - count of overdue items
    - workload breakdown per named owner
    """
    # 1. Total meetings
    total_meetings = db.query(Meeting).filter(Meeting.user_id == current_user.id).count()

    # 2. Total action items
    action_items = (
        db.query(ActionItem)
        .join(Meeting, ActionItem.meeting_id == Meeting.id)
        .filter(Meeting.user_id == current_user.id)
        .all()
    )
    total_action_items = len(action_items)

    # 3. Clarification percentage
    clarification_count = sum(1 for item in action_items if item.needs_clarification)
    clarification_percentage = 0.0
    if total_action_items > 0:
        clarification_percentage = round((clarification_count / total_action_items) * 100.0, 1)

    # 4. Overdue items
    today = date.today()
    overdue_items = sum(
        1 for item in action_items
        if item.deadline and item.deadline < today and item.status != ItemStatus.DONE.value
    )

    # 5. Workload breakdown by owner (exclude None / empty / unassigned)
    workload_map = defaultdict(int)
    for item in action_items:
        if item.owner and item.owner.strip() and item.owner.lower() not in ("null", "none", "unassigned", "unclear"):
            workload_map[item.owner.strip()] += 1

    workload = [
        OwnerWorkload(owner=owner, task_count=count)
        for owner, count in sorted(workload_map.items(), key=lambda x: x[1], reverse=True)
    ]

    per_owner_dict = dict(workload_map)

    return StatsResponse(
        total_meetings=total_meetings,
        total_action_items=total_action_items,
        clarification_percentage=clarification_percentage,
        overdue_count=overdue_items,
        overdue_items=overdue_items,
        per_owner=per_owner_dict,
        workload=workload
    )

