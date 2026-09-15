import os
import sys
import json
from datetime import date

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.extraction import extract_meeting_data, is_duplicate_action_item, validate_and_normalize_extraction

SAMPLE_TRANSCRIPT = """Priya: Okay so for the launch next week, I'll handle the press release, should be done by Thursday.
Sam: I can take the social media graphics, I'll have drafts by Wednesday.
Priya: Great. Someone needs to update the pricing page too, but I'm not sure who's free for that.
Rahul: I could maybe look at it if no one else can, but I have the client call all week.
Priya: Let's flag that one. Also we need the QA pass done before Friday's release.
Sam: I think that's on the QA team but honestly I don't know who exactly picks that up.
Priya: Okay, let's note that as unclear too. Last thing - can someone send the launch email to the mailing list?
Rahul: Yeah I'll do that, I'll send it Friday morning right before the release goes live.
Priya: Also, we've decided to push the enterprise pricing tier discussion to next quarter.
Sam: Agreed, and we're keeping the current logo for this launch instead of the redesign."""

def mock_llm_success(prompt: str) -> str:
    """Mock LLM returning high-fidelity structured JSON matching gpt-4o-mini behavior."""
    return json.dumps({
        "action_items": [
            {
                "task": "Handle the press release for launch",
                "owner": "Priya",
                "deadline": "2026-09-17",
                "confidence": 0.95,
                "priority": "High",
                "category": "Marketing",
                "source_sentence": "Priya: Okay so for the launch next week, I'll handle the press release, should be done by Thursday."
            },
            {
                "task": "Create drafts for social media graphics",
                "owner": "Sam",
                "deadline": "2026-09-16",
                "confidence": 0.90,
                "priority": "Medium",
                "category": "Marketing",
                "source_sentence": "Sam: I can take the social media graphics, I'll have drafts by Wednesday."
            },
            {
                "task": "Update the pricing page",
                "owner": None,
                "deadline": None,
                "confidence": 0.40,
                "priority": "Medium",
                "category": "Engineering",
                "source_sentence": "Priya: Great. Someone needs to update the pricing page too, but I'm not sure who's free for that."
            },
            {
                "task": "Complete QA pass before release",
                "owner": None,
                "deadline": "2026-09-18",
                "confidence": 0.45,
                "priority": "High",
                "category": "Engineering",
                "source_sentence": "Priya: Let's flag that one. Also we need the QA pass done before Friday's release."
            },
            {
                "task": "Send launch email to the mailing list",
                "owner": "Rahul",
                "deadline": "2026-09-18",
                "confidence": 0.90,
                "priority": "High",
                "category": "Marketing",
                "source_sentence": "Rahul: Yeah I'll do that, I'll send it Friday morning right before the release goes live."
            }
        ],
        "decisions": [
            {
                "decision": "Push the enterprise pricing tier discussion to next quarter",
                "context": "Agreed by Priya and team to defer enterprise pricing tier"
            },
            {
                "decision": "Keep the current logo for this launch instead of the redesign",
                "context": "Agreed by Sam and team"
            }
        ],
        "sentiment": "smooth"
    })

def mock_llm_failure(prompt: str) -> str:
    """Mock LLM that raises an error / returns malformed string."""
    raise ConnectionError("OpenAI API rate limit / timeout / invalid JSON simulation")


def run_stage3_tests():
    print("==================================================================")
    print("=== Stage 3: Standalone AI Extraction Pipeline Test Suite ===")
    print("==================================================================")
    
    reference_date = date(2026, 9, 14)

    # -------------------------------------------------------------
    # 1. TEST A: LLM SUCCESS PATH (Full Extraction on Sample Transcript)
    # -------------------------------------------------------------
    print("\n--- [TEST A] LLM Success Path on EXACT Sample Transcript ---")
    result_a = extract_meeting_data(
        transcript=SAMPLE_TRANSCRIPT,
        confidence_threshold=0.75,
        llm_caller=mock_llm_success,
        reference_date=reference_date
    )

    print("\nParsed Extraction Output (JSON):")
    print(json.dumps(result_a, indent=2))

    action_items = result_a["action_items"]
    decisions = result_a["decisions"]
    sentiment = result_a["sentiment"]

    assert len(action_items) == 5, f"Expected 5 action items, got {len(action_items)}"
    assert len(decisions) == 2, f"Expected 2 decisions, got {len(decisions)}"
    assert sentiment in ("smooth", "neutral", "tense")

    # Check Clear Items
    clear_items = [item for item in action_items if not item["needs_clarification"]]
    assert len(clear_items) == 3, f"Expected 3 clear items, got {len(clear_items)}"
    assert any(i["owner"] == "Priya" and "press release" in i["task"].lower() for i in clear_items)
    assert any(i["owner"] == "Sam" and "graphics" in i["task"].lower() for i in clear_items)
    assert any(i["owner"] == "Rahul" and "email" in i["task"].lower() for i in clear_items)

    # Check Ambiguous Items
    unclear_items = [item for item in action_items if item["needs_clarification"]]
    assert len(unclear_items) == 2, f"Expected 2 unclear items, got {len(unclear_items)}"
    assert any("pricing" in i["task"].lower() and i["owner"] is None for i in unclear_items)
    assert any("qa" in i["task"].lower() and i["owner"] is None for i in unclear_items)

    # Check Decisions
    assert any("enterprise" in d["decision"].lower() for d in decisions)
    assert any("logo" in d["decision"].lower() for d in decisions)

    print("\n[PASS] Test A: Exact sample transcript parsed correctly with 3 finalized, 2 clarification items, 2 decisions, sentiment.")

    # -------------------------------------------------------------
    # 2. TEST B: FALLBACK EXTRACTOR PATH (LLM Failure / Malformed JSON)
    # -------------------------------------------------------------
    print("\n--- [TEST B] Fallback Extractor Path (LLM Failure Simulation) ---")
    result_b = extract_meeting_data(
        transcript=SAMPLE_TRANSCRIPT,
        confidence_threshold=0.75,
        llm_caller=mock_llm_failure,
        reference_date=reference_date
    )

    print("\nFallback Extracted Output (JSON):")
    print(json.dumps(result_b, indent=2))

    assert "action_items" in result_b
    assert len(result_b["action_items"]) > 0, "Fallback extractor failed to extract items"
    for fb_item in result_b["action_items"]:
        assert fb_item["confidence"] == 0.3
        assert fb_item["priority"] == "Medium"
        assert fb_item["category"] == "General"
        assert fb_item["needs_clarification"] is True
        assert fb_item["source_sentence"] is not None

    print("\n[PASS] Test B: Fallback extractor returned valid degraded extraction without crashing.")

    # -------------------------------------------------------------
    # 3. TEST C: PAST DEADLINE VALIDATION
    # -------------------------------------------------------------
    print("\n--- [TEST C] Past Deadline Clarification Rule ---")
    past_date_data = {
        "action_items": [
            {
                "task": "Submit Q2 retrospective",
                "owner": "Sarah",
                "deadline": "2020-01-01",  # In the past
                "confidence": 0.95,        # High confidence
                "priority": "High",
                "category": "General",
                "source_sentence": "Sarah: I'll submit the Q2 retro by Jan 2020."
            }
        ],
        "decisions": [],
        "sentiment": "neutral"
    }
    validated_past = validate_and_normalize_extraction(past_date_data, confidence_threshold=0.75, reference_date=reference_date)
    item = validated_past["action_items"][0]
    print(f"Past deadline item needs_clarification: {item['needs_clarification']} (confidence={item['confidence']}, deadline={item['deadline']})")
    assert item["needs_clarification"] is True, "Past deadline must force needs_clarification = True"
    print("[PASS] Test C: Past deadline rule successfully forced needs_clarification=True.")

    # -------------------------------------------------------------
    # 4. TEST D: DUPLICATE DETECTION PURE FUNCTION
    # -------------------------------------------------------------
    print("\n--- [TEST D] Pure Duplicate Detection Function (SequenceMatcher > 0.75) ---")
    
    # Matching task & matching owner -> True
    match1 = is_duplicate_action_item(
        "Draft and finalize the press release", "Priya",
        "Draft and finalize press release for launch", "Priya",
        threshold=0.75
    )
    print(f"1. Similar task, same owner ('Priya'): {match1}")
    assert match1 is True

    # Matching task & both owners None -> True
    match2 = is_duplicate_action_item(
        "Update the pricing page", None,
        "Update the website pricing page", None,
        threshold=0.75
    )
    print(f"2. Similar task, both owners None: {match2}")
    assert match2 is True

    # Matching task, DIFFERENT owner -> False
    match3 = is_duplicate_action_item(
        "Draft and finalize the press release", "Priya",
        "Draft and finalize the press release", "Sam",
        threshold=0.75
    )
    print(f"3. Same task, different owner ('Priya' vs 'Sam'): {match3}")
    assert match3 is False

    # Completely different task, same owner -> False
    match4 = is_duplicate_action_item(
        "Draft the press release", "Priya",
        "Fix production database outage", "Priya",
        threshold=0.75
    )
    print(f"4. Completely different task, same owner: {match4}")
    assert match4 is False

    print("[PASS] Test D: Duplicate matching pure function behaves as specified.")

    print("\n==================================================================")
    print("=== ALL STAGE 3 TESTS PASSED SUCCESSFULLY ===")
    print("==================================================================")
    return True

if __name__ == "__main__":
    run_stage3_tests()
