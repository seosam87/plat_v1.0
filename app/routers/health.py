"""Health check endpoint."""
from fastapi import APIRouter
from sqlalchemy import text

from app.database import AsyncSessionLocal

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """Check DB, Redis, and return component status. Returns 503 if any is down."""
    from fastapi.responses import JSONResponse

    checks = {}

    # DB check
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"

    # Redis check
    try:
        import redis
        from app.config import settings
        r = redis.from_url(settings.REDIS_URL, socket_timeout=3)
        r.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"

    # Celery check
    try:
        from app.celery_app import celery_app
        insp = celery_app.control.inspect(timeout=3)
        active = insp.active()
        checks["celery"] = "ok" if active is not None else "no workers"
    except Exception as exc:
        checks["celery"] = f"error: {exc}"

    all_ok = all(v == "ok" for v in checks.values())
    status_code = 200 if all_ok else 503

    return JSONResponse(content={"status": "healthy" if all_ok else "degraded", "checks": checks}, status_code=status_code)
