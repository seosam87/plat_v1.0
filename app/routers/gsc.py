"""GSC router: OAuth 2.0 flow + Search Analytics fetch."""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.dependencies import get_db
from app.models.user import User
from app.services import gsc_service
from app.services.site_service import get_site

router = APIRouter(prefix="/gsc", tags=["gsc"])


@router.get("/authorize/{site_id}")
async def gsc_authorize(
    site_id: uuid.UUID,
    _: User = Depends(require_admin),
) -> dict:
    """Return the Google OAuth2 authorization URL for a site."""
    url = gsc_service.build_authorize_url(str(site_id))
    return {"authorize_url": url, "site_id": str(site_id)}


@router.get("/callback", name="gsc_callback")
async def gsc_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """OAuth2 callback: exchange code for tokens, save encrypted."""
    site_id = uuid.UUID(state)
    site = await get_site(db, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    token_data = await gsc_service.exchange_code(code)
    await gsc_service.save_tokens(db, site_id, token_data)
    await db.commit()

    return {"status": "connected", "site_id": str(site_id)}


@router.post("/{site_id}/fetch")
async def fetch_gsc_data(
    site_id: uuid.UUID,
    days: int = 28,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Fetch Search Analytics data for a site (last N days)."""
    site = await get_site(db, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    access_token = await gsc_service.get_valid_token(db, site_id)
    if not access_token:
        raise HTTPException(status_code=400, detail="GSC not connected. Complete OAuth flow first.")

    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days)

    # GSC uses site URL with trailing slash for domain properties
    site_url = site.url.rstrip("/") + "/"
    rows = await gsc_service.fetch_search_analytics(
        access_token,
        site_url,
        start_date.isoformat(),
        end_date.isoformat(),
    )

    return {
        "site_id": str(site_id),
        "period": f"{start_date} — {end_date}",
        "row_count": len(rows),
        "rows": rows[:100],  # first 100 for API response; full data saved in Phase 06
    }
