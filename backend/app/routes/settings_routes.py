from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import ConfidenceThresholdRequest, UserResponse
from app.auth import get_current_user

router = APIRouter(prefix="/settings", tags=["Settings"])

@router.post("/confidence-threshold", response_model=UserResponse)
def update_confidence_threshold(
    request: ConfidenceThresholdRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Updates the per-user confidence threshold for triggering 'needs clarification'.
    """
    current_user.confidence_threshold = request.threshold
    db.commit()
    db.refresh(current_user)
    return current_user

@router.get("/confidence-threshold")
def get_confidence_threshold(current_user: User = Depends(get_current_user)):
    """
    Returns the current user's configured confidence threshold.
    """
    return {"confidence_threshold": current_user.confidence_threshold}
