import sys
import subprocess
import time

TESTS = [
    ("Stage 2 Authentication", "backend/test_stage2_auth.py"),
    ("Stage 3 AI Extraction", "backend/test_stage3_extraction.py"),
    ("Stage 4 Meetings Pipeline", "backend/test_stage4_meetings.py"),
    ("Stage 5A Action Items", "backend/test_stage5a_action_items.py"),
    ("Stage 5B Decisions Log", "backend/test_stage5b_decisions.py"),
    ("Stage 5C Dashboard Stats", "backend/test_stage5c_stats.py"),
    ("Stage 5D Calendar Timeline", "backend/test_stage5d_calendar.py"),
    ("Stage 5E CSV & PDF Exports", "backend/test_stage5e_exports.py"),
    ("Stage 6 WebSocket Real-Time", "backend/test_stage6_websocket.py"),
    ("Stage 7 Background Scheduler", "backend/test_stage7_scheduler.py"),
    ("Stage 8 Full E2E Integration", "backend/test_stage8_integration.py"),
    ("Stage 9 Quality Hardening", "backend/test_stage9_verification.py"),
    ("n8n Workflow Integration", "backend/test_n8n_integration.py"),
]


def main():
    print("=" * 70, flush=True)
    print("=== FULL SYSTEM REGRESSION & VERIFICATION RUNNER ===", flush=True)
    print("=" * 70, flush=True)
    
    start_total = time.time()
    results = {}
    
    for name, test_path in TESTS:
        print(f"\n[RUNNING] {name} ({test_path})...", flush=True)
        t0 = time.time()
        res = subprocess.run([sys.executable, test_path], capture_output=True, text=True)
        duration = time.time() - t0
        
        if res.returncode == 0:
            print(f"[PASS] {name} ({duration:.2f}s)", flush=True)
            results[name] = ("PASS", duration, "")
        else:
            print(f"[FAIL] {name} ({duration:.2f}s)", flush=True)
            error_preview = (res.stderr or res.stdout)[-300:]
            print(f"Error: {error_preview}", flush=True)
            results[name] = ("FAIL", duration, error_preview)
            
    total_duration = time.time() - start_total
    
    print("\n" + "=" * 70, flush=True)
    print("=== FINAL VERIFICATION SUMMARY ===", flush=True)
    print("=" * 70, flush=True)
    all_passed = True
    for name, (status, duration, err) in results.items():
        print(f"{name:35} : [{status}] ({duration:.2f}s)", flush=True)
        if status != "PASS":
            all_passed = False
            
    print("-" * 70, flush=True)
    print(f"Total Execution Time: {total_duration:.2f}s", flush=True)
    if all_passed:
        print("RESULT: ALL 12 TEST SUITES PASSED (100% SUCCESS)", flush=True)
        print("STAGE 10 COMPLETE — DEMO READY", flush=True)
        sys.exit(0)
    else:
        print("RESULT: SOME TESTS FAILED", flush=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
