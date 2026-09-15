import logging
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, date, timedelta, timezone
from typing import Set, Tuple, Optional, Any, Dict
from sqlalchemy.orm import Session
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.database import SessionLocal
from app.models import ActionItem, ClarificationRequest, Meeting, User, ItemStatus, utc_now
from app.websocket_manager import manager

logger = logging.getLogger("background_scheduler")

# In-memory tracking to avoid duplicate overdue notifications within the same day: (action_item_id, YYYY-MM-DD)
_notified_overdue_today: Set[Tuple[int, str]] = set()

scheduler: Optional[AsyncIOScheduler] = None

def resolve_owner_email(owner_str: Optional[str], meeting_user_id: int, db: Session) -> Optional[str]:
    """
    Safely determines whether a valid email can be associated with an action item owner.
    - If owner_str contains '@' and matches a registered user's email, returns that email.
    - If owner_str matches the username prefix of a registered user's email, returns that email.
    - If owner_str matches the meeting creator's email prefix, returns the creator's email.
    - Returns None otherwise to prevent sending emails to arbitrary unverified strings.
    """
    if not owner_str or not owner_str.strip():
        return None

    clean_owner = owner_str.strip().lower()

    # 1. If owner string is formatted as an email
    if "@" in clean_owner:
        user = db.query(User).filter(User.email.ilike(clean_owner)).first()
        if user:
            return user.email
        return None

    # 2. Check all registered users to match email prefix (e.g. "priya" -> "priya@example.com")
    users = db.query(User).all()
    for u in users:
        u_email_prefix = u.email.split("@")[0].lower()
        if clean_owner == u_email_prefix:
            return u.email

    # 3. Check meeting creator
    meeting_user = db.query(User).filter(User.id == meeting_user_id).first()
    if meeting_user and meeting_user.email:
        if clean_owner == meeting_user.email.split("@")[0].lower():
            return meeting_user.email

    return None

def send_email_notification(to_email: str, subject: str, body: str) -> bool:
    """
    Attempts to send email via smtplib if SMTP is configured.
    Falls back gracefully to logging if SMTP is unconfigured or fails.
    """
    if not settings.SMTP_HOST:
        logger.info(f"[EMAIL NOT CONFIGURED] To: {to_email} | Subject: '{subject}'")
        return False

    smtp_user = settings.effective_smtp_user
    smtp_from = settings.effective_smtp_from

    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = smtp_from
        msg["To"] = to_email

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=5) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if smtp_user and settings.SMTP_PASSWORD:
                server.login(smtp_user, settings.SMTP_PASSWORD)
            server.sendmail(smtp_from, [to_email], msg.as_string())
        logger.info(f"Email successfully sent to {to_email}")
        return True
    except Exception as e:
        logger.warning(f"SMTP email sending failed to {to_email}: {e}")
        return False

async def run_daily_overdue_check():
    """
    Job 1: Daily Overdue Check.
    Finds action items where deadline < today and status != 'done'.
    Notifies owner via Email (if safely resolved) or logs reminder and broadcasts WebSocket event.
    """
    logger.info("Overdue check started")
    today = date.today()
    today_str = today.isoformat()
    db = SessionLocal()
    try:
        overdue_items = (
            db.query(ActionItem)
            .join(Meeting, ActionItem.meeting_id == Meeting.id)
            .filter(
                ActionItem.deadline != None,
                ActionItem.deadline < today,
                ActionItem.status != ItemStatus.DONE.value
            )
            .all()
        )

        logger.info(f"Found {len(overdue_items)} overdue action items.")

        for item in overdue_items:
            try:
                notify_key = (item.id, today_str)
                if notify_key in _notified_overdue_today:
                    continue  # Already notified today

                user_id = item.meeting.user_id
                recipient_email = resolve_owner_email(item.owner, user_id, db)

                subject = f"Overdue Action Item: {item.task[:40]}"
                body = (
                    f"Hello,\n\n"
                    f"The following action item is overdue:\n"
                    f"Task: {item.task}\n"
                    f"Deadline: {item.deadline}\n"
                    f"Priority: {item.priority}\n"
                    f"Status: {item.status}\n\n"
                    f"Please update or complete this item in your dashboard."
                )

                email_sent = False
                if recipient_email:
                    email_sent = send_email_notification(recipient_email, subject, body)

                if email_sent:
                    logger.info(f"Overdue notification email sent for item #{item.id} to {recipient_email}")
                else:
                    logger.info(f"Overdue reminder: Item #{item.id} '{item.task}' (Owner: {item.owner}, Deadline: {item.deadline}) is overdue.")

                # Broadcast WebSocket event to item's authenticated user
                try:
                    await manager.broadcast_to_user(user_id, {
                        "event": "action_item.overdue",
                        "data": {
                            "id": item.id,
                            "meeting_id": item.meeting_id,
                            "task": item.task,
                            "owner": item.owner,
                            "deadline": item.deadline.isoformat() if item.deadline else None,
                            "status": item.status
                        }
                    })
                except Exception as ws_err:
                    logger.warning(f"Failed to broadcast overdue WS event for item {item.id}: {ws_err}")

                _notified_overdue_today.add(notify_key)
                logger.info(f"Overdue notification sent for item #{item.id}")

            except Exception as item_err:
                logger.error(f"Error processing overdue item #{item.id}: {item_err}")
                continue

    except Exception as e:
        logger.error(f"Error in run_daily_overdue_check: {e}")
    finally:
        db.close()

# Alias for testing convenience
run_overdue_check = run_daily_overdue_check

async def run_clarification_reminder_check():
    """
    Job 2: Clarification Reminder Check.
    Finds clarification_requests where answered_at IS NULL, question_sent_at <= 24h ago,
    and reminder_sent_at IS NULL.
    Sends reminder via Email / Console + WebSocket and updates reminder_sent_at.
    """
    logger.info("Clarification reminder check started")
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    db = SessionLocal()
    try:
        pending_requests = (
            db.query(ClarificationRequest)
            .join(ActionItem, ClarificationRequest.action_item_id == ActionItem.id)
            .join(Meeting, ActionItem.meeting_id == Meeting.id)
            .filter(
                ClarificationRequest.answered_at == None,
                ClarificationRequest.question_sent_at <= cutoff,
                ClarificationRequest.reminder_sent_at == None
            )
            .all()
        )

        logger.info(f"Found {len(pending_requests)} pending clarification reminders.")

        now = utc_now()
        for req in pending_requests:
            try:
                item = req.action_item
                user_id = item.meeting.user_id
                user = db.query(User).filter(User.id == user_id).first()

                recipient_email = resolve_owner_email(item.owner, user_id, db)
                if not recipient_email and user:
                    recipient_email = user.email

                subject = f"Clarification Reminder: {item.task[:40]}"
                body = (
                    f"Hello,\n\n"
                    f"The following action item still needs clarification (owner/deadline):\n"
                    f"Task: {item.task}\n\n"
                    f"Please visit your 'Needs Clarification' queue to confirm missing details."
                )

                email_sent = False
                if recipient_email:
                    email_sent = send_email_notification(recipient_email, subject, body)

                if email_sent:
                    logger.info(f"Clarification reminder email sent for request #{req.id} to {recipient_email}")
                else:
                    logger.info(f"Clarification reminder: Item #{item.id} '{item.task}' requires clarification.")

                # Mark reminder as sent in DB first
                req.reminder_sent_at = now
                db.commit()

                # Broadcast WebSocket event (fail-safe)
                try:
                    await manager.broadcast_to_user(user_id, {
                        "event": "clarification.reminder",
                        "data": {
                            "action_item_id": item.id,
                            "question_sent_at": req.question_sent_at.isoformat() if req.question_sent_at else None,
                            "reminder_sent_at": req.reminder_sent_at.isoformat() if req.reminder_sent_at else None
                        }
                    })
                except Exception as ws_err:
                    logger.warning(f"Failed to broadcast clarification reminder WS event for request #{req.id}: {ws_err}")

                logger.info(f"Clarification reminder sent for request #{req.id}")

            except Exception as item_err:
                db.rollback()
                logger.error(f"Error processing clarification reminder #{req.id}: {item_err}")
                continue

    except Exception as e:
        logger.error(f"Error in run_clarification_reminder_check: {e}")
    finally:
        db.close()

# Alias for testing convenience
run_clarification_reminder = run_clarification_reminder_check

import asyncio

def start_scheduler(test_mode: bool = False, loop=None):
    """Initializes and starts the background AsyncIOScheduler."""
    global scheduler
    if scheduler is not None and scheduler.running:
        return scheduler

    try:
        current_loop = loop or asyncio.get_running_loop()
    except RuntimeError:
        try:
            current_loop = asyncio.get_event_loop()
        except RuntimeError:
            current_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(current_loop)

    scheduler = AsyncIOScheduler(event_loop=current_loop)

    if test_mode:
        # 30-second interval for testing mode
        scheduler.add_job(run_daily_overdue_check, IntervalTrigger(seconds=30), id="daily_overdue_check")
        scheduler.add_job(run_clarification_reminder_check, IntervalTrigger(seconds=30), id="clarification_reminder_check")
        logger.info("Scheduler started (TEST MODE: 30s intervals)")
    else:
        # Production intervals: daily overdue check and hourly clarification reminder
        scheduler.add_job(run_daily_overdue_check, IntervalTrigger(hours=24), id="daily_overdue_check")
        scheduler.add_job(run_clarification_reminder_check, IntervalTrigger(hours=1), id="clarification_reminder_check")
        logger.info("Scheduler started (PRODUCTION MODE: 24h/1h intervals)")

    scheduler.start()
    return scheduler

def shutdown_scheduler():
    """Stops the scheduler cleanly."""
    global scheduler
    if scheduler is not None and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
        scheduler = None
