"""Etho Services.

Deliberately no eager re-exports: importing the data layer (pet_store,
vet_report, breed_reference) must not require the AI stack (google.genai,
cv2, ultralytics) — scripts/seed_demo.py and the test suites rely on that.
Import service modules directly, e.g. `from .services.gemini_service
import analyze_video`.
"""
