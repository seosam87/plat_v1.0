"""Tools stub router: index page with empty states for all 6 Phase 24-25 tools."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.template_engine import templates

router = APIRouter(prefix="/ui/tools", tags=["tools"])


@router.get("/", response_class=HTMLResponse, name="tools_index")
async def tools_index(request: Request) -> HTMLResponse:
    """Tools index page with empty states for upcoming Phase 24-25 tools."""
    return templates.TemplateResponse(
        request,
        "tools/index.html",
        {},
    )
