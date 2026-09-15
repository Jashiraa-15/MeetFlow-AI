import difflib
from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Meeting, ActionItem, ClarificationRequest, ItemPriority, ItemStatus, utc_now
from app.schemas import (
    ActionItemResponse, ActionItemUpdateRequest, MergeActionItemsRequest,
    DuplicateCandidateResponse
)
from app.auth import get_current_user
from app.websocket_manager import manager

router = APIRouter(prefix="/action-items", tags=["Action Items"])

ALLOWED_PRIORITIES = {"High", "Medium", "Low"}
ALLOWED_CATEGORIES = {"Engineering", "Marketing", "General"}
ALLOWED_STATUSES = {"todo", "in_progress", "done"}

@router.get("", response_model=List[ActionItemResponse])
def list_action_items(
    status: Optional[str] = Query(None),
    owner: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    needs_clarification: Optional[bool] = Query(None),
    overdue: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists action items across all meetings belonging to the authenticated user.
    Supports filtering by status, owner, category, needs_clarification, and overdue.
    """
    query = (
        db.query(ActionItem)
        .join(Meeting, ActionItem.meeting_id == Meeting.id)
        .filter(Meeting.user_id == current_user.id)
    )

    if status:
        query = query.filter(ActionItem.status == status.lower().strip())
    
    if owner:
        query = query.filter(ActionItem.owner.ilike(owner.strip()))

    if category:
        query = query.filter(ActionItem.category.ilike(category.strip()))

    if needs_clarification is not None:
        query = query.filter(ActionItem.needs_clarification == needs_clarification)

    if overdue is True:
        today = date.today()
        query = query.filter(
            ActionItem.deadline != None,
            ActionItem.deadline < today,
            ActionItem.status != ItemStatus.DONE.value
        )

    return query.order_by(ActionItem.created_at.desc()).all()

@router.patch("/{id}", response_model=ActionItemResponse)
async def update_action_item(
    id: int,
    updates: ActionItemUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Updates editable fields of an action item.
    If update fills in previously-null owner/deadline such that ambiguity is resolved,
    sets needs_clarification = False and is_confirmed = True.
    Broadcasts action_item.updated over WebSockets.
    """
    item = (
        db.query(ActionItem)
        .join(Meeting, ActionItem.meeting_id == Meeting.id)
        .filter(ActionItem.id == id, Meeting.user_id == current_user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action item not found")

    update_data = updates.model_dump(exclude_unset=True)

    # Validate enums
    if "priority" in update_data and update_data["priority"] is not None:
        p_val = update_data["priority"].capitalize()
        if p_val not in ALLOWED_PRIORITIES:
            raise HTTPException(status_code=400, detail=f"Invalid priority '{update_data['priority']}'. Allowed: High, Medium, Low")
        update_data["priority"] = p_val

    if "category" in update_data and update_data["category"] is not None:
        c_val = update_data["category"].capitalize()
        if c_val not in ALLOWED_CATEGORIES:
            raise HTTPException(status_code=400, detail=f"Invalid category '{update_data['category']}'. Allowed: Engineering, Marketing, General")
        update_data["category"] = c_val

    if "status" in update_data and update_data["status"] is not None:
        s_val = update_data["status"].lower()
        if s_val not in ALLOWED_STATUSES:
            raise HTTPException(status_code=400, detail=f"Invalid status '{update_data['status']}'. Allowed: todo, in_progress, done")
        update_data["status"] = s_val

    prev_owner_null = (item.owner is None or item.owner.strip() == "")
    prev_deadline_null = (item.deadline is None)

    for field, value in update_data.items():
        setattr(item, field, value)

    owner_now_filled = bool(item.owner and item.owner.strip())
    deadline_now_filled = bool(item.deadline)

    if (prev_owner_null and owner_now_filled) or (prev_deadline_null and deadline_now_filled):
        if owner_now_filled and deadline_now_filled and "needs_clarification" not in update_data:
            item.needs_clarification = False
            item.is_confirmed = True

    item.updated_at = utc_now()
    db.commit()
    db.refresh(item)

    # Broadcast event
    try:
        await manager.broadcast_to_user(current_user.id, {
            "event": "action_item.updated",
            "data": ActionItemResponse.model_validate(item).model_dump()
        })
    except Exception:
        pass

    return item

@router.post("/{id}/confirm", response_model=ActionItemResponse)
async def confirm_action_item(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Confirms an action item.
    Role check: Admins can confirm any user's item; members can confirm ONLY their own item.
    Broadcasts action_item.confirmed over WebSockets to item owner (and admin if different).
    """
    item = (
        db.query(ActionItem)
        .join(Meeting, ActionItem.meeting_id == Meeting.id)
        .filter(ActionItem.id == id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action item not found")

    is_owner = (item.meeting.user_id == current_user.id)
    is_admin = (current_user.role == "admin")

    if not is_owner and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to confirm another user's action item"
        )

    item.is_confirmed = True
    item.needs_clarification = False
    item.updated_at = utc_now()
    db.commit()
    db.refresh(item)

    # Broadcast to item owner and confirming user
    try:
        recipients = [item.meeting.user_id]
        if current_user.id not in recipients:
            recipients.append(current_user.id)
        await manager.broadcast_to_users(recipients, {
            "event": "action_item.confirmed",
            "data": {
                "id": item.id,
                "meeting_id": item.meeting_id,
                "is_confirmed": True,
                "needs_clarification": False
            }
        })
    except Exception:
        pass

    return item

@router.post("/merge", response_model=ActionItemResponse)
async def merge_action_items(
    request: MergeActionItemsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Merges duplicate action item into primary action item.
    Transfers missing info, increments mention_count, and deletes duplicate.
    Broadcasts action_item.updated and action_item.deleted.
    """
    primary = (
        db.query(ActionItem)
        .join(Meeting, ActionItem.meeting_id == Meeting.id)
        .filter(ActionItem.id == request.primary_id, Meeting.user_id == current_user.id)
        .first()
    )
    duplicate = (
        db.query(ActionItem)
        .join(Meeting, ActionItem.meeting_id == Meeting.id)
        .filter(ActionItem.id == request.duplicate_id, Meeting.user_id == current_user.id)
        .first()
    )

    if not primary:
        raise HTTPException(status_code=404, detail=f"Primary action item #{request.primary_id} not found")
    if not duplicate:
        raise HTTPException(status_code=404, detail=f"Duplicate action item #{request.duplicate_id} not found")
    if primary.id == duplicate.id:
        raise HTTPException(status_code=400, detail="Cannot merge an action item into itself")

    # Transfer information if primary has missing fields
    if not primary.owner and duplicate.owner:
        primary.owner = duplicate.owner
    if not primary.deadline and duplicate.deadline:
        primary.deadline = duplicate.deadline
    if primary.needs_clarification and not duplicate.needs_clarification:
        primary.needs_clarification = False
        primary.is_confirmed = True

    primary.mention_count += duplicate.mention_count
    primary.updated_at = utc_now()
    dup_id = duplicate.id

    db.delete(duplicate)
    db.commit()
    db.refresh(primary)

    # Broadcast real-time updates
    try:
        await manager.broadcast_to_user(current_user.id, {
            "event": "action_item.updated",
            "data": ActionItemResponse.model_validate(primary).model_dump()
        })
        await manager.broadcast_to_user(current_user.id, {
            "event": "action_item.deleted",
            "data": {
                "deleted_item_id": dup_id
            }
        })
    except Exception:
        pass

    return primary


@router.get("/duplicates/{id}", response_model=List[DuplicateCandidateResponse])
def get_duplicate_candidates(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Finds candidate duplicate action items belonging to the authenticated user (SequenceMatcher ratio > 0.6 + owner match).
    """
    target = (
        db.query(ActionItem)
        .join(Meeting, ActionItem.meeting_id == Meeting.id)
        .filter(ActionItem.id == id, Meeting.user_id == current_user.id)
        .first()
    )
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action item not found")

    other_items = (
        db.query(ActionItem)
        .join(Meeting, ActionItem.meeting_id == Meeting.id)
        .filter(Meeting.user_id == current_user.id, ActionItem.id != id)
        .all()
    )

    candidates: List[DuplicateCandidateResponse] = []
    for item in other_items:
        ratio = difflib.SequenceMatcher(
            None,
            target.task.lower().strip(),
            item.task.lower().strip()
        ).ratio()

        if ratio > 0.6:
            owners_match = (
                (target.owner is None or item.owner is None) or
                (target.owner and item.owner and target.owner.lower().strip() == item.owner.lower().strip())
            )
            if owners_match:
                candidates.append(DuplicateCandidateResponse(
                    id=item.id,
                    task=item.task,
                    owner=item.owner,
                    deadline=item.deadline,
                    similarity_score=round(ratio, 2),
                    meeting_id=item.meeting_id
                ))

    return sorted(candidates, key=lambda x: x.similarity_score, reverse=True)
