import time
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from fastapi import HTTPException, status
from app.config import settings

# In-memory store for rate limiting: user_id -> list of submission timestamps
_rate_limit_store: Dict[int, List[float]] = {}

# In-memory store for identical transcript cache: (user_id, sha256_hash) -> (timestamp, extraction_result)
_transcript_cache: Dict[Tuple[int, str], Tuple[float, Dict[str, Any]]] = {}

def check_meeting_rate_limit(user_id: int) -> None:
    """
    Enforces rate limit: max MAX_MEETING_SUBMISSIONS_PER_HOUR submissions per user per rolling hour.
    Raises HTTP 429 if exceeded.
    """
    now = time.time()
    one_hour_ago = now - 3600.0

    timestamps = _rate_limit_store.get(user_id, [])
    # Keep only timestamps within the rolling hour window
    recent_timestamps = [ts for ts in timestamps if ts > one_hour_ago]

    max_allowed = settings.MAX_MEETING_SUBMISSIONS_PER_HOUR
    if len(recent_timestamps) >= max_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: maximum {max_allowed} meeting submissions per hour"
        )
    
    recent_timestamps.append(now)
    _rate_limit_store[user_id] = recent_timestamps

def hash_transcript(transcript: str) -> str:
    """Computes SHA-256 hex digest of normalized transcript text."""
    normalized = " ".join(transcript.strip().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

def get_cached_extraction(user_id: int, transcript: str) -> Optional[Dict[str, Any]]:
    """
    Returns cached extraction result for this user if submitted within the last hour.
    """
    t_hash = hash_transcript(transcript)
    key = (user_id, t_hash)

    if key in _transcript_cache:
        cached_time, cached_result = _transcript_cache[key]
        if time.time() - cached_time < settings.CACHE_EXPIRY_SECONDS:
            return cached_result
        else:
            del _transcript_cache[key]
    return None

def set_cached_extraction(user_id: int, transcript: str, result: Dict[str, Any]) -> None:
    """Caches extraction result for 1 hour for the specified user."""
    t_hash = hash_transcript(transcript)
    key = (user_id, t_hash)
    _transcript_cache[key] = (time.time(), result)

def clear_cache_and_limits_for_tests() -> None:
    """Helper to reset rate limits and caches during testing."""
    _rate_limit_store.clear()
    _transcript_cache.clear()
