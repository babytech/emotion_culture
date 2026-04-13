from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from app.api.analyze import router as analyze_router
from app.api.auth import router as auth_router
from app.api.bootstrap import router as bootstrap_router
from app.api.checkin import router as checkin_router
from app.api.email import router as email_router
from app.api.favorites import router as favorites_router
from app.api.health import router as health_router
from app.api.history import router as history_router
from app.api.media_generate import router as media_generate_router
from app.api.retention import router as retention_router
from app.api.report import router as report_router
from app.api.settings import router as settings_router
from app.api.stt import router as stt_router
from app.api.study_quiz import router as study_quiz_router
from app.api.today_history import router as today_history_router

# Load local env file for development.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
CORE_IMAGES_DIR = Path(__file__).resolve().parent / "core" / "images"


app = FastAPI(
    title="Emotion Culture WeChat API",
    description="Backend skeleton for the WeChat mini program.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api", tags=["health"])
app.include_router(auth_router, prefix="/api", tags=["auth"])
app.include_router(bootstrap_router, prefix="/api", tags=["bootstrap"])
app.include_router(checkin_router, prefix="/api", tags=["checkin"])
app.include_router(analyze_router, prefix="/api", tags=["analyze"])
app.include_router(email_router, prefix="/api", tags=["email"])
app.include_router(favorites_router, prefix="/api", tags=["favorites"])
app.include_router(history_router, prefix="/api", tags=["history"])
app.include_router(retention_router, prefix="/api", tags=["retention-manage"])
app.include_router(report_router, prefix="/api", tags=["retention"])
app.include_router(settings_router, prefix="/api", tags=["settings"])
app.include_router(stt_router, prefix="/api", tags=["stt"])
app.include_router(media_generate_router, prefix="/api", tags=["media-generate"])
app.include_router(today_history_router, prefix="/api", tags=["today-history"])
app.include_router(study_quiz_router, prefix="/api", tags=["study-quiz"])

if CORE_IMAGES_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(CORE_IMAGES_DIR)), name="assets")


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "emotion-culture-wechat-api", "status": "ok"}
