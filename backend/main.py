from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base

from app.routes.auth_routes import router as auth_router
from app.routes.meeting_routes import router as meeting_router
from app.routes.action_item_routes import router as action_item_router
from app.routes.decision_routes import router as decision_router
from app.routes.stats_routes import router as stats_router
from app.routes.calendar_routes import router as calendar_router
from app.routes.export_routes import router as export_router
from app.routes.settings_routes import router as settings_router
from app.routes.ws_routes import router as ws_router
from app.routes.webhook_routes import router as webhook_router
from app.scheduler import start_scheduler, shutdown_scheduler

# Initialize database tables
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages application startup and shutdown lifecycle (e.g. background scheduler)."""
    # Startup: Start APScheduler
    start_scheduler(test_mode=False)
    yield
    # Shutdown: Cleanly stop APScheduler
    shutdown_scheduler()

app = FastAPI(
    title=settings.APP_NAME,
    description="Backend API for MeetFlow AI",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register All API Routers
app.include_router(auth_router)
app.include_router(meeting_router)
app.include_router(action_item_router)
app.include_router(decision_router)
app.include_router(stats_router)
app.include_router(calendar_router)
app.include_router(export_router)
app.include_router(settings_router)
app.include_router(ws_router)
app.include_router(webhook_router)


@app.get("/")
def root():
    return {"message": "MeetFlow AI Backend", "status": "running"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
