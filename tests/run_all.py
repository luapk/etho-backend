"""Run all Etho test suites (stdlib runner, no pytest needed).

The suites stub the heavy AI deps (google.generativeai, cv2) so they run
anywhere Python + fastapi + httpx are installed:

    pip install -r requirements-dev.txt
    PYTHONPATH=. python tests/run_all.py

Each suite uses a throwaway DATA_DIR — your real database is never touched.
"""
import subprocess, sys, os

SUITES = ["test_longitudinal.py", "test_auth_quality.py", "test_timeline_weight.py",
          "test_model_selector.py", "test_capture_batch.py", "test_media_store.py", "test_reading_image.py", "test_breed_health.py",
          "test_annotator_caption.py", "test_identity_check.py"]

here = os.path.dirname(os.path.abspath(__file__))
root = os.path.dirname(here)
failed = []
for suite in SUITES:
    print(f"\n{'='*60}\n{suite}\n{'='*60}")
    env = {**os.environ, "PYTHONPATH": root}
    rc = subprocess.run([sys.executable, os.path.join(here, suite)], env=env).returncode
    if rc != 0:
        failed.append(suite)

print(f"\n{'='*60}")
if failed:
    print("FAILED:", ", ".join(failed)); sys.exit(1)
print("All suites passed.")
