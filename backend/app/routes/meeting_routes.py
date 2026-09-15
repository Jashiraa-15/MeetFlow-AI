import io
import difflib
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
import docx

from app.database import get_db
from app.models import User, Meeting, ActionItem, Decision, ClarificationRequest, utc_now
from app.schemas import (
    MeetingResponse, MeetingCreateRequest, MeetingSummaryResponse,
    PaginatedMeetingsResponse, ActionItemResponse
)
from app.auth import get_current_user
from app.extraction import extract_meeting_data
from app.transcription import transcribe_audio
from app.cache_and_limiter import (
    check_meeting_rate_limit,
    get_cached_extraction,
    set_cached_extraction
)
from app.websocket_manager import manager

router = APIRouter(prefix="/meetings", tags=["Meetings"])

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".webm", ".flac", ".aac"}
ALLOWED_EXTENSIONS = {".txt", ".docx"}.union(AUDIO_EXTENSIONS)

@router.post("", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
async def create_meeting(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Creates a new meeting by processing transcript text, uploaded .txt/.docx, or audio file.
    Runs extraction pipeline, duplicate detection, and clarification tracking.
    Broadcasts real-time WebSocket events (meeting.created, action_item.created).
    """
    # 1. Enforce Rate Limiting (max 10 submissions/hour/user)
    check_meeting_rate_limit(current_user.id)

    content_type = request.headers.get("content-type", "")
    transcript_text: str = ""
    title: Optional[str] = None
    meeting_date: date = date.today()

    # 2. Extract Transcript & Metadata from Request
    if content_type.startswith("application/json"):
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON payload")
        
        transcript_text = str(body.get("transcript_text", "")).strip()
        if not transcript_text:
            raise HTTPException(status_code=400, detail="transcript_text cannot be empty")
        
        title = body.get("title")
        if body.get("meeting_date"):
            try:
                meeting_date = datetime.strptime(body["meeting_date"], "%Y-%m-%d").date()
            except ValueError:
                pass

    elif content_type.startswith("multipart/form-data"):
        form = await request.form()
        uploaded_file = form.get("file")
        title = form.get("title")
        if form.get("meeting_date"):
            try:
                meeting_date = datetime.strptime(str(form.get("meeting_date")), "%Y-%m-%d").date()
            except ValueError:
                pass

        if uploaded_file and hasattr(uploaded_file, "filename") and uploaded_file.filename:
            filename = uploaded_file.filename
            ext = "." + filename.split(".")[-1].lower() if "." in filename else ""

            if ext not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported file format '{ext}'. Allowed formats: .txt, .docx, audio files ({', '.join(sorted(AUDIO_EXTENSIONS))})"
                )

            file_bytes = await uploaded_file.read()
            if not file_bytes:
                raise HTTPException(status_code=400, detail="Uploaded file is empty")

            if ext == ".txt":
                try:
                    transcript_text = file_bytes.decode("utf-8").strip()
                except UnicodeDecodeError:
                    transcript_text = file_bytes.decode("latin-1", errors="ignore").strip()

            elif ext == ".docx":
                try:
                    doc = docx.Document(io.BytesIO(file_bytes))
                    transcript_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip()).strip()
                except Exception as docx_err:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Failed to parse .docx file: {docx_err}"
                    )

            elif ext in AUDIO_EXTENSIONS:
                try:
                    transcript_text = transcribe_audio(file_bytes, filename)
                except Exception as audio_err:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Audio transcription failed: {audio_err}"
                    )
        else:
            transcript_text = str(form.get("transcript_text", "")).strip()

        if not transcript_text:
            raise HTTPException(status_code=400, detail="No transcript text or file content provided")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request Content-Type must be 'application/json' or 'multipart/form-data'"
        )

    # 3. Check Identical Transcript Cache (1-hour window for current user)
    cached_result = get_cached_extraction(current_user.id, transcript_text)
    if cached_result is not None:
        extraction_data = cached_result
    else:
        threshold = current_user.confidence_threshold if current_user.confidence_threshold else 0.75
        extraction_data = extract_meeting_data(
            transcript=transcript_text,
            confidence_threshold=threshold,
            reference_date=meeting_date
        )
        set_cached_extraction(current_user.id, transcript_text, extraction_data)

    # 4. Transactional Database Insertion
    try:
        default_title = title if (title and title.strip()) else f"Meeting - {meeting_date.isoformat()}"
        sentiment = extraction_data.get("sentiment", "neutral")

        new_meeting = Meeting(
            user_id=current_user.id,
            title=default_title,
            transcript_text=transcript_text,
            meeting_date=meeting_date,
            sentiment=sentiment,
            created_at=utc_now()
        )
        db.add(new_meeting)
        db.flush()

        # 5. Fetch all existing action items for this user across previous meetings for duplicate detection
        existing_user_items = (
            db.query(ActionItem)
            .join(Meeting, ActionItem.meeting_id == Meeting.id)
            .filter(Meeting.user_id == current_user.id)
            .filter(ActionItem.meeting_id != new_meeting.id)
            .all()
        )

        now = utc_now()
        created_action_items: List[ActionItem] = []
        updated_action_items: List[ActionItem] = []

        # 6. Save Action Items with Duplicate Detection
        for item in extraction_data.get("action_items", []):
            task_text = item["task"]
            new_owner = item.get("owner")
            
            is_duplicate = False
            duplicate_target: Optional[ActionItem] = None

            for existing_item in existing_user_items:
                sim_ratio = difflib.SequenceMatcher(
                    None,
                    task_text.lower().strip(),
                    existing_item.task.lower().strip()
                ).ratio()

                if sim_ratio > 0.75:
                    existing_owner = existing_item.owner
                    owners_match = (
                        (new_owner is None and existing_owner is None) or
                        (new_owner and existing_owner and new_owner.lower().strip() == existing_owner.lower().strip())
                    )
                    if owners_match:
                        is_duplicate = True
                        duplicate_target = existing_item
                        break

            if is_duplicate and duplicate_target is not None:
                duplicate_target.mention_count += 1
                duplicate_target.updated_at = now
                db.add(duplicate_target)
                updated_action_items.append(duplicate_target)
            else:
                parsed_deadline = None
                if item.get("deadline"):
                    try:
                        parsed_deadline = datetime.strptime(item["deadline"], "%Y-%m-%d").date()
                    except ValueError:
                        parsed_deadline = None

                new_action_item = ActionItem(
                    meeting_id=new_meeting.id,
                    task=task_text,
                    owner=new_owner,
                    deadline=parsed_deadline,
                    priority=item.get("priority", "Medium"),
                    category=item.get("category", "General"),
                    confidence=item.get("confidence", 1.0),
                    needs_clarification=item.get("needs_clarification", False),
                    is_confirmed=False,
                    is_duplicate_of=None,
                    source_sentence=item.get("source_sentence"),
                    status="todo",
                    mention_count=1,
                    created_at=now,
                    updated_at=now
                )
                db.add(new_action_item)
                db.flush()
                created_action_items.append(new_action_item)

                if new_action_item.needs_clarification:
                    clarification_req = ClarificationRequest(
                        action_item_id=new_action_item.id,
                        question_sent_at=now,
                        answered_at=None,
                        reminder_sent_at=None
                    )
                    db.add(clarification_req)

        # 7. Save Decisions
        for dec in extraction_data.get("decisions", []):
            new_decision = Decision(
                meeting_id=new_meeting.id,
                decision_text=dec.get("decision", ""),
                context=dec.get("context"),
                created_at=now
            )
            db.add(new_decision)

        db.commit()
        db.refresh(new_meeting)
    except Exception as db_err:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create meeting transaction: {db_err}"
        )


    # 8. Real-time WebSocket Broadcasts (fail-safe)
    try:
        await manager.broadcast_to_user(current_user.id, {
            "event": "meeting.processed",
            "data": {
                "meeting_id": new_meeting.id,
                "action_items_created": len(created_action_items),
                "decisions_created": len(extraction_data.get("decisions", [])),
                "clarification_count": sum(1 for item in created_action_items if item.needs_clarification)
            }
        })
        for item_obj in created_action_items:
            await manager.broadcast_to_user(current_user.id, {
                "event": "action_item.created",
                "data": ActionItemResponse.model_validate(item_obj).model_dump()
            })
        for dup_obj in updated_action_items:
            await manager.broadcast_to_user(current_user.id, {
                "event": "action_item.updated",
                "data": ActionItemResponse.model_validate(dup_obj).model_dump()
            })
    except Exception as ws_err:
        pass  # Never let WS failures disrupt HTTP response

    return new_meeting


@router.get("", response_model=PaginatedMeetingsResponse)
def list_meetings(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists meetings for the authenticated user with pagination and search.
    Search matches across transcript text and action item task text.
    """
    query = db.query(Meeting).filter(Meeting.user_id == current_user.id)

    if search and search.strip():
        term = f"%{search.strip()}%"
        matching_task_meetings = (
            db.query(ActionItem.meeting_id)
            .join(Meeting, ActionItem.meeting_id == Meeting.id)
            .filter(Meeting.user_id == current_user.id)
            .filter(ActionItem.task.ilike(term))
        )
        query = query.filter(
            (Meeting.transcript_text.ilike(term)) | (Meeting.id.in_(matching_task_meetings))
        )

    total = query.count()
    meetings = query.order_by(Meeting.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for m in meetings:
        items.append(MeetingSummaryResponse(
            id=m.id,
            title=m.title,
            meeting_date=m.meeting_date,
            sentiment=m.sentiment,
            created_at=m.created_at,
            action_item_count=len(m.action_items),
            decision_count=len(m.decisions)
        ))

    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    return PaginatedMeetingsResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )

@router.get("/{id}", response_model=MeetingResponse)
def get_meeting_detail(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves full details of a specific meeting for the authenticated user.
    Returns 404 if the meeting doesn't exist or belongs to another user.
    """
    meeting = db.query(Meeting).filter(Meeting.id == id, Meeting.user_id == current_user.id).first()
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    return meeting

@router.get("/{id}/recurring-items", response_model=List[ActionItemResponse])
def get_recurring_items(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Cross-references action items in this meeting with past meetings to identify recurring unresolved items.
    """
    meeting = db.query(Meeting).filter(Meeting.id == id, Meeting.user_id == current_user.id).first()
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    
    recurring = [item for item in meeting.action_items if item.mention_count > 1 and item.status != "done"]
    return recurring
