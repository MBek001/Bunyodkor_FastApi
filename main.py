from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
import pytz  # ✅ Qo'shildi
from app.routers import (
    auth,
    users,
    roles,
    students,
    groups,
    contracts,
    transactions,
    coach,
    gate,
    reports,
    settings,
    import_router,
    backup,
    waiting_list,
    uploads,
    archive,
    click,
    payme,
)
from app.services.backup import backup_service
from app.core.config import settings as app_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ✅ Timezone configuration
timezone = pytz.timezone(app_settings.TIMEZONE)  # "Asia/Tashkent"

# Initialize scheduler with timezone
scheduler = AsyncIOScheduler(timezone=timezone)  # ✅ Timezone qo'shildi


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown events.
    """
    # Startup
    logger.info("Starting Bunyodkor CIMS API...")

    # Initialize backup scheduler if enabled
    if app_settings.BACKUP_ENABLED:
        logger.info(
            f"Backup enabled - scheduling daily backups at {app_settings.BACKUP_HOUR}:00 "
            f"({app_settings.TIMEZONE})"  # ✅ Timezone ko'rsatish
        )

        # Schedule backup to run daily at specified hour in Tashkent timezone
        scheduler.add_job(
            backup_service.run_backup,
            trigger=CronTrigger(
                hour=app_settings.BACKUP_HOUR,
                minute=0,
                timezone=timezone  # ✅ Timezone qo'shildi
            ),
            id="daily_backup",
            name="Daily Database Backup",
            replace_existing=True,
        )

        # Start the scheduler
        scheduler.start()
        logger.info(
            f"Backup scheduler started - next run at {app_settings.BACKUP_HOUR}:00 "
            f"{app_settings.TIMEZONE}"
        )

        # ✅ Keyingi backup vaqtini ko'rsatish
        next_run = scheduler.get_job("daily_backup").next_run_time
        logger.info(f"Next backup scheduled for: {next_run}")
    else:
        logger.info("Backup is disabled in configuration")

    yield

    # Shutdown
    logger.info("Shutting down Bunyodkor CIMS API...")
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Backup scheduler stopped")


app = FastAPI(
    title="BUNYODKOR CIMS API",
    description="Comprehensive management system for Bunyodkor Football Academy",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint with scheduler status"""
    scheduler_status = "running" if scheduler.running else "stopped"
    next_backup = None

    if scheduler.running and app_settings.BACKUP_ENABLED:
        job = scheduler.get_job("daily_backup")
        if job:
            next_backup = job.next_run_time.isoformat() if job.next_run_time else None

    return {
        "status": "ok",
        "service": "bunyodkor-cims",
        "scheduler": scheduler_status,
        "backup_enabled": app_settings.BACKUP_ENABLED,
        "next_backup": next_backup,
        "timezone": app_settings.TIMEZONE
    }


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(roles.router)
app.include_router(students.router)
app.include_router(groups.router)
app.include_router(contracts.router)
app.include_router(transactions.router)
app.include_router(coach.router)
app.include_router(gate.router)
app.include_router(reports.router)
app.include_router(settings.router)
app.include_router(import_router.router)
app.include_router(backup.router)
app.include_router(waiting_list.router)
app.include_router(uploads.router)
app.include_router(archive.router)
app.include_router(click.router)
app.include_router(payme.router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8008, reload=True)