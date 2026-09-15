import re
import json
import difflib
import logging
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Callable

from app.llm import call_llm

logger = logging.getLogger("meeting_extractor")

EXTRACTION_SYSTEM_PROMPT = """You are an expert executive meeting assistant and task extraction specialist.
Your task is to analyze the meeting transcript, identify genuine action items (tasks), explicit decisions, and overall conversational sentiment.

You MUST return ONLY a valid JSON object in this exact shape:
{
  "action_items": [
    {
      "task": "string",
      "owner": "string or null",
      "deadline": "YYYY-MM-DD or null",
      "confidence": float (0.0 to 1.0),
      "priority": "High" | "Medium" | "Low",
      "category": "Engineering" | "Marketing" | "General",
      "source_sentence": "the exact line from the transcript this came from"
    }
  ],
  "decisions": [
    {
      "decision": "string",
      "context": "string"
    }
  ],
  "sentiment": "tense" | "smooth" | "neutral"
}

STRICT EXTRACTION RULES:
1. Extract genuine action items only. Do not turn ordinary conversation, suggestions, rhetorical questions, or acknowledgements into tasks.
2. Owner resolution:
   - If an owner is clearly assigned or volunteers (e.g. "I'll handle the press release" spoken by Priya -> owner: "Priya").
   - If owner is missing, vague, or explicitly uncertain (e.g. "Someone needs to update the pricing page" or "I think that's on the QA team but honestly I don't know who exactly picks that up"), set owner to null.
   - If someone merely hedges (e.g. Rahul saying "I could maybe look at it if no one else can, but I have the client call all week"), this is NOT an owner assignment; keep owner as null.
3. Deadline resolution:
   - Output valid ISO date YYYY-MM-DD when a specific day or date is stated relative to the reference date provided in the user prompt.
   - If deadline is missing or vague, output null.
4. Confidence scoring:
   - High confidence (0.80 to 0.95): when BOTH owner and deadline/commitment are explicit and clear.
   - Low confidence (0.30 to 0.50): when owner or deadline is missing, unassigned, vague, or explicitly uncertain.
5. Priority:
   - "High" if urgency language appears (e.g. urgent, blocker, ASAP, critical, before release, right before).
   - Otherwise "Medium" or "Low".
6. Category: Must be one of "Engineering", "Marketing", "General".
7. Decisions: Extract explicit organizational or team decisions (e.g., deferrals, architecture choices, branding/logo choices) separately from action items. Provide the context for each decision.
8. Sentiment: Classify conversational atmosphere as "tense", "smooth", or "neutral" based on word choice, tension, and productivity.
9. Source sentence: MUST match the exact line from the transcript where the task/decision was stated.
10. Do not invent tasks, owners, or deadlines that were not in the transcript. Output ONLY valid JSON with no markdown formatting.
"""

def is_duplicate_action_item(
    task1: str,
    owner1: Optional[str],
    task2: str,
    owner2: Optional[str],
    threshold: float = 0.75
) -> bool:
    """
    Pure function for duplicate action item matching.
    Returns True if difflib similarity ratio > threshold (0.75) AND owners match (or both are null).
    """
    t1 = task1.strip().lower()
    t2 = task2.strip().lower()

    similarity = difflib.SequenceMatcher(None, t1, t2).ratio()
    if similarity <= threshold:
        return False

    o1 = (owner1 or "").strip().lower()
    o2 = (owner2 or "").strip().lower()

    return o1 == o2

def fallback_extractor(transcript: str) -> Dict[str, Any]:
    """
    Deterministic regex-based fallback extractor according to specification.
    Scans transcript line-by-line for action keywords and decision patterns if LLM fails or returns invalid JSON.
    Guarantees a valid degraded extraction structure without failing the request.
    """
    action_items: List[Dict[str, Any]] = []
    decisions: List[Dict[str, Any]] = []
    
    # Patterns for genuine action intent
    self_assignment_pattern = re.compile(r"\b(I'll|I will|can take|will handle)\b", re.IGNORECASE)
    unassigned_pattern = re.compile(r"\b(someone needs to|we need)\b", re.IGNORECASE)
    decision_pattern = re.compile(r"\b(decided to|we've decided|agreed,|keeping the current)\b", re.IGNORECASE)
    speaker_pattern = re.compile(r"^([A-Za-z0-9_\s]+):")

    for line in transcript.strip().splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue

        speaker_match = speaker_pattern.match(line_clean)
        speaker = speaker_match.group(1).strip() if speaker_match else None
        
        # Check for decisions
        if decision_pattern.search(line_clean):
            dec_text = line_clean
            if speaker_match:
                dec_text = line_clean[speaker_match.end():].strip()
            dec_text = re.sub(r"^(Also,\s*|Agreed,\s*and\s*)", "", dec_text, flags=re.IGNORECASE).strip()
            decisions.append({
                "decision": dec_text,
                "context": f"Mentioned by {speaker}" if speaker else "Discussed in meeting"
            })
            continue

        # Check for action items
        is_action = False
        owner = None

        if self_assignment_pattern.search(line_clean):
            # Check for false positive hedging (e.g., "if no one else can")
            if not re.search(r"\bif no one else can\b", line_clean, re.IGNORECASE):
                is_action = True
                owner = speaker
        elif unassigned_pattern.search(line_clean):
            is_action = True
            owner = None

        if is_action:
            task_text = line_clean
            if speaker_match:
                task_text = line_clean[speaker_match.end():].strip()
            
            # Remove leading conversational prefixes/fillers
            task_text = re.sub(
                r"^(Okay so for the launch next week,|Great\.|Also\s*we\s*need|Also|Yeah|Last thing\s*-\s*|can someone\s*)",
                "",
                task_text,
                flags=re.IGNORECASE
            ).strip()

            action_items.append({
                "task": task_text if task_text else line_clean,
                "owner": owner,
                "deadline": None,
                "confidence": 0.3,
                "priority": "Medium",
                "category": "General",
                "source_sentence": line_clean,
                "needs_clarification": True
            })

    return {
        "action_items": action_items,
        "decisions": decisions,
        "sentiment": "neutral"
    }

def validate_and_normalize_extraction(
    data: Dict[str, Any],
    confidence_threshold: float = 0.75,
    reference_date: Optional[date] = None
) -> Dict[str, Any]:
    """
    Validates, sanitizes, and applies confidence/clarification and past-deadline logic
    to extracted meeting data.
    """
    if reference_date is None:
        reference_date = date.today()

    if not isinstance(data, dict):
        raise ValueError("Extraction data must be a JSON object")
    
    raw_action_items = data.get("action_items")
    if not isinstance(raw_action_items, list):
        raw_action_items = []

    raw_decisions = data.get("decisions")
    if not isinstance(raw_decisions, list):
        raw_decisions = []

    sentiment = str(data.get("sentiment", "neutral")).lower().strip()
    if sentiment not in ("tense", "smooth", "neutral"):
        sentiment = "neutral"

    normalized_items: List[Dict[str, Any]] = []
    for item in raw_action_items:
        if not isinstance(item, dict):
            continue

        task = str(item.get("task", "")).strip()
        if not task:
            continue

        owner = item.get("owner")
        if owner is not None:
            owner = str(owner).strip()
            if owner.lower() in ("null", "none", "unknown", "unclear", "unassigned", ""):
                owner = None

        deadline_str = item.get("deadline")
        parsed_deadline: Optional[date] = None
        if deadline_str is not None:
            deadline_str = str(deadline_str).strip()
            if deadline_str.lower() in ("null", "none", "unclear", ""):
                deadline_str = None
            else:
                try:
                    parsed_deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()
                except ValueError:
                    deadline_str = None

        try:
            confidence = float(item.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))
        except (ValueError, TypeError):
            confidence = 0.5

        priority = str(item.get("priority", "Medium")).strip().capitalize()
        if priority not in ("High", "Medium", "Low"):
            priority = "Medium"

        category = str(item.get("category", "General")).strip().capitalize()
        if category not in ("Engineering", "Marketing", "General"):
            category = "General"

        source_sentence = str(item.get("source_sentence", "")).strip() or task

        # Needs Clarification Logic:
        # 1. confidence < confidence_threshold
        # 2. owner missing/null
        # 3. deadline missing/null
        # 4. deadline is before reference_date (past deadline check)
        needs_clarification = False
        if confidence < confidence_threshold:
            needs_clarification = True
        elif owner is None or owner.strip() == "":
            needs_clarification = True
        elif deadline_str is None:
            needs_clarification = True
        elif parsed_deadline and parsed_deadline < reference_date:
            needs_clarification = True

        normalized_items.append({
            "task": task,
            "owner": owner,
            "deadline": deadline_str,
            "confidence": round(confidence, 2),
            "priority": priority,
            "category": category,
            "source_sentence": source_sentence,
            "needs_clarification": needs_clarification
        })

    normalized_decisions: List[Dict[str, Any]] = []
    for d in raw_decisions:
        if not isinstance(d, dict):
            continue
        decision_text = str(d.get("decision", d.get("decision_text", ""))).strip()
        if not decision_text:
            continue
        context = str(d.get("context", "")).strip() or None
        normalized_decisions.append({
            "decision": decision_text,
            "context": context
        })

    return {
        "action_items": normalized_items,
        "decisions": normalized_decisions,
        "sentiment": sentiment
    }

def extract_meeting_data(
    transcript: str,
    confidence_threshold: float = 0.75,
    llm_caller: Optional[Callable[[str], str]] = None,
    reference_date: Optional[date] = None
) -> Dict[str, Any]:
    """
    Complete standalone extraction pipeline:
    1. Builds unified prompt with instructions and transcript.
    2. Sends prompt to LLM via swappable call_llm(prompt: str) -> str.
    3. Parses & validates JSON response.
    4. Falls back to deterministic regex extractor on any error or invalid JSON.
    5. Evaluates confidence thresholds, missing owners/deadlines, and past dates.
    """
    if reference_date is None:
        reference_date = date.today()

    if llm_caller is None:
        llm_caller = call_llm

    full_prompt = f"""{EXTRACTION_SYSTEM_PROMPT}

Reference Date (Today): {reference_date.isoformat()}

Meeting Transcript:
---
{transcript}
---

Output ONLY the JSON object conforming to the required schema."""

    try:
        raw_response = llm_caller(full_prompt)
        
        # Clean potential markdown wrapping (e.g. ```json ... ```)
        cleaned_json = raw_response.strip()
        if cleaned_json.startswith("```"):
            cleaned_json = re.sub(r"^```(?:json)?\s*", "", cleaned_json)
            cleaned_json = re.sub(r"\s*```$", "", cleaned_json)

        parsed_data = json.loads(cleaned_json)
        validated_data = validate_and_normalize_extraction(
            parsed_data,
            confidence_threshold=confidence_threshold,
            reference_date=reference_date
        )
        return validated_data

    except Exception as e:
        logger.warning(f"LLM extraction failed or returned invalid JSON ({e}). Running fallback extractor.")
        fallback_data = fallback_extractor(transcript)
        return validate_and_normalize_extraction(
            fallback_data,
            confidence_threshold=confidence_threshold,
            reference_date=reference_date
        )


