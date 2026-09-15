import logging
import hmac
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request, status
from sqlalchemy.orm import Session
import httpx

from app.database import get_db
from app.config import settings
from app.models import ActionItem, ClarificationRequest, Meeting, utc_now
from app.schemas import ActionItemResponse, N8nClarificationWebhookRequest
from app.websocket_manager import manager

logger = logging.getLogger("webhook_routes")

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

ALLOWED_PRIORITIES = {"High", "Medium", "Low"}
ALLOWED_CATEGORIES = {"Engineering", "Marketing", "General"}

def verify_n8n_secret(
    x_webhook_secret: Optional[str] = Header(None, alias="X-Webhook-Secret"),
    secret: Optional[str] = Query(None)
):
    """
    Verifies that the incoming request provides a valid n8n webhook secret.
    Accepts via 'X-Webhook-Secret' header or '?secret=' query parameter.
    """
    provided_secret = x_webhook_secret or secret
    expected_secret = settings.N8N_WEBHOOK_SECRET

    if not provided_secret or not hmac.compare_digest(provided_secret.strip(), expected_secret.strip()):
        logger.warning("Unauthorized n8n webhook attempt: invalid or missing secret.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing webhook secret."
        )
    return True

@router.get("/n8n/health")
def n8n_webhook_health():
    """
    Health check endpoint for the n8n integration bridge.
    """
    return {
        "status": "ok",
        "service": "n8n-webhook-bridge",
        "webhook_enabled": bool(settings.N8N_WEBHOOK_SECRET),
        "outbound_url_configured": bool(settings.N8N_CLARIFICATION_WEBHOOK_URL)
    }

@router.post("/n8n/clarification", response_model=ActionItemResponse)
async def receive_n8n_clarification(
    payload: N8nClarificationWebhookRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_n8n_secret)
):
    """
    Receives human clarification results from the n8n 'Meeting Transcript -> Action Items' workflow.
    Updates the targeted ActionItem, marks ambiguity as resolved, updates ClarificationRequest,
    and broadcasts real-time WebSocket events to the user's React frontend.
    """
    item = (
        db.query(ActionItem)
        .join(Meeting, ActionItem.meeting_id == Meeting.id)
        .filter(ActionItem.id == payload.action_item_id)
        .first()
    )

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ActionItem #{payload.action_item_id} not found."
        )

    # 1. Update owner if provided
    if payload.owner is not None:
        clean_owner = payload.owner.strip()
        item.owner = clean_owner if clean_owner else None

    # 2. Update deadline if provided
    if payload.deadline is not None:
        item.deadline = payload.deadline

    # 3. Update priority if provided & valid
    if payload.priority is not None:
        p_val = payload.priority.capitalize()
        if p_val in ALLOWED_PRIORITIES:
            item.priority = p_val

    # 4. Update category if provided & valid
    if payload.category is not None:
        c_val = payload.category.capitalize()
        if c_val in ALLOWED_CATEGORIES:
            item.category = c_val

    # 5. Apply resolution flags
    if payload.is_confirmed:
        item.is_confirmed = True
        item.needs_clarification = False

    item.updated_at = utc_now()

    # 6. Update pending clarification requests for this action item
    pending_requests = (
        db.query(ClarificationRequest)
        .filter(
            ClarificationRequest.action_item_id == item.id,
            ClarificationRequest.answered_at == None
        )
        .all()
    )
    for req in pending_requests:
        req.answered_at = item.updated_at

    db.commit()
    db.refresh(item)

    # 7. Real-time WebSocket broadcasts to user's React application
    try:
        user_id = item.meeting.user_id
        # Broadcast action_item.updated
        await manager.broadcast_to_user(user_id, {
            "event": "action_item.updated",
            "data": ActionItemResponse.model_validate(item).model_dump()
        })

        # If confirmed, broadcast action_item.confirmed
        if item.is_confirmed:
            await manager.broadcast_to_user(user_id, {
                "event": "action_item.confirmed",
                "data": {
                    "id": item.id,
                    "meeting_id": item.meeting_id,
                    "is_confirmed": True,
                    "needs_clarification": False,
                    "source": "n8n_clarification"
                }
            })
    except Exception as ws_err:
        logger.warning(f"Failed to broadcast WebSocket update for n8n clarification: {ws_err}")

    logger.info(f"Successfully processed n8n clarification for ActionItem #{item.id} (Owner: {item.owner}, Deadline: {item.deadline})")
    return item

async def trigger_n8n_clarification_webhook(
    action_item: ActionItem,
    meeting: Meeting,
    callback_base_url: Optional[str] = None
) -> bool:
    """
    Asynchronously fires an outbound clarification request to n8n if N8N_CLARIFICATION_WEBHOOK_URL is configured.
    Fail-safe: will log warnings upon failure but will never raise or disrupt the primary flow.
    """
    if not settings.N8N_CLARIFICATION_WEBHOOK_URL:
        return False

    callback_url = (
        f"{callback_base_url.rstrip('/')}/api/webhooks/n8n/clarification"
        if callback_base_url
        else "/api/webhooks/n8n/clarification"
    )

    missing_fields = []
    if not action_item.owner:
        missing_fields.append("owner")
    if not action_item.deadline:
        missing_fields.append("deadline")

    payload = {
        "action_item_id": action_item.id,
        "meeting_id": meeting.id,
        "user_id": meeting.user_id,
        "meeting_title": meeting.title,
        "task": action_item.task,
        "source_sentence": action_item.source_sentence,
        "priority": action_item.priority,
        "category": action_item.category,
        "missing_fields": missing_fields,
        "callback_url": callback_url
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            headers = {"X-Webhook-Secret": settings.N8N_WEBHOOK_SECRET}
            resp = await client.post(settings.N8N_CLARIFICATION_WEBHOOK_URL, json=payload, headers=headers)
            if resp.status_code in (200, 201, 202):
                logger.info(f"Dispatched n8n clarification webhook for ActionItem #{action_item.id}")
                return True
            else:
                logger.warning(f"n8n webhook returned non-200 status {resp.status_code} for ActionItem #{action_item.id}")
                return False
    except Exception as e:
        logger.warning(f"Failed to trigger n8n clarification webhook for ActionItem #{action_item.id}: {e}")
        return False
