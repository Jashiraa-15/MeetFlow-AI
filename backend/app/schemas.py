from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field

# Authentication Schemas
class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters")
    role: Optional[str] = "member"

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, description="Password cannot be empty")

class UserResponse(BaseModel):
    id: int
    email: str
    role: str
    confidence_threshold: float
    created_at: datetime

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# Action Item Schemas
class ActionItemResponse(BaseModel):
    id: int
    meeting_id: int
    task: str
    owner: Optional[str] = None
    deadline: Optional[date] = None
    priority: str
    category: str
    confidence: float
    needs_clarification: bool
    is_confirmed: bool
    is_duplicate_of: Optional[int] = None
    source_sentence: Optional[str] = None
    status: str
    mention_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ActionItemUpdateRequest(BaseModel):
    task: Optional[str] = None
    owner: Optional[str] = None
    deadline: Optional[date] = None
    priority: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    needs_clarification: Optional[bool] = None
    is_confirmed: Optional[bool] = None

class MergeActionItemsRequest(BaseModel):
    primary_id: int
    duplicate_id: int

class DuplicateCandidateResponse(BaseModel):
    id: int
    task: str
    owner: Optional[str] = None
    deadline: Optional[date] = None
    similarity_score: float
    meeting_id: int

# Decision Schemas
class DecisionResponse(BaseModel):
    id: int
    meeting_id: int
    decision_text: str
    context: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# Clarification Request Schemas
class ClarificationRequestResponse(BaseModel):
    id: int
    action_item_id: int
    question_sent_at: datetime
    answered_at: Optional[datetime] = None
    reminder_sent_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# n8n Webhook Schemas
class N8nClarificationWebhookRequest(BaseModel):
    action_item_id: int = Field(..., description="ID of the ActionItem to resolve")
    owner: Optional[str] = Field(None, description="Assigned owner from human clarification")
    deadline: Optional[date] = Field(None, description="Resolved deadline from human clarification")
    priority: Optional[str] = Field(None, description="Updated priority (High, Medium, Low)")
    category: Optional[str] = Field(None, description="Updated category")
    is_confirmed: Optional[bool] = Field(True, description="Whether the action item is confirmed")
    notes: Optional[str] = Field(None, description="Optional clarification context/notes from human response")


# Meeting Schemas
class MeetingCreateRequest(BaseModel):
    transcript_text: str = Field(..., min_length=1, description="Raw transcript text")
    title: Optional[str] = None
    meeting_date: Optional[date] = None

class MeetingResponse(BaseModel):
    id: int
    user_id: int
    title: Optional[str] = None
    transcript_text: str
    meeting_date: date
    sentiment: Optional[str] = None
    created_at: datetime
    action_items: List[ActionItemResponse] = []
    decisions: List[DecisionResponse] = []

    class Config:
        from_attributes = True

class MeetingSummaryResponse(BaseModel):
    id: int
    title: Optional[str] = None
    meeting_date: date
    sentiment: Optional[str] = None
    created_at: datetime
    action_item_count: int
    decision_count: int

    class Config:
        from_attributes = True

class PaginatedMeetingsResponse(BaseModel):
    items: List[MeetingSummaryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

# Stats Schema
class OwnerWorkload(BaseModel):
    owner: str
    task_count: int

class StatsResponse(BaseModel):
    total_meetings: int
    total_action_items: int
    clarification_percentage: float
    overdue_count: int
    overdue_items: int
    per_owner: Dict[str, int]
    workload: List[OwnerWorkload]


# Settings Schema
class ConfidenceThresholdRequest(BaseModel):
    threshold: float = Field(..., ge=0.0, le=1.0, description="Confidence threshold between 0.0 and 1.0")
