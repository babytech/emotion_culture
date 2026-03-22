import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
PC_APP_DIR = REPO_ROOT / "apps" / "pc"

if not PC_APP_DIR.exists():
    raise RuntimeError(f"PC app directory not found: {PC_APP_DIR}")

if str(PC_APP_DIR) not in sys.path:
    sys.path.insert(0, str(PC_APP_DIR))


from culture import CultureManager  # type: ignore  # noqa: E402
from email_utils import send_analysis_email  # type: ignore  # noqa: E402
from emotion import (  # type: ignore  # noqa: E402
    analyze_text_sentiment,
    comfort_text,
    detect_face_emotion,
    guochao_characters,
)
from speech import analyze_speech_emotion  # type: ignore  # noqa: E402
