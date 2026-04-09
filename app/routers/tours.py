"""Tour API — advertises scenario YAML files that carry a `tour:` block.

Browser-side tour.js (phase 19.2) fetches these endpoints to discover
tours for the current page and to load the full step list. YAML parsing
and Pydantic validation happen server-side; the browser gets JSON.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

import yaml
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import require_admin
from app.models.user import User
from app.services.scenario_schema import Scenario

router = APIRouter(prefix="/api/tours", tags=["tours"])

# /opt/seo-platform/app/routers/tours.py -> parents[2] == /opt/seo-platform
SCENARIOS_DIR = Path(__file__).resolve().parents[2] / "scenarios"


@lru_cache(maxsize=1)
def _load_all_tours() -> List[Scenario]:
    """Load every scenarios/*.yaml, return only those with a tour: block.

    Cached for the uvicorn process lifetime. New tours require a restart —
    documented in scenarios/README.md (Plan 05).
    """
    out: List[Scenario] = []
    if not SCENARIOS_DIR.is_dir():
        return out
    for yaml_file in sorted(SCENARIOS_DIR.glob("*.yaml")):
        try:
            raw = yaml.safe_load(yaml_file.read_text())
            sc = Scenario.model_validate(raw)
        except Exception:
            # Malformed scenario files are owned by the 19.1 runner's
            # collector, which will surface the error there. Don't
            # take down the tour API because of an unrelated bad file.
            continue
        if sc.tour is not None:
            out.append(sc)
    return out


@router.get("/")
async def list_tours(
    page: str = Query(..., description="location.pathname to match against tour.entry_url"),
    _user: User = Depends(require_admin),
):
    return [
        {
            "name": t.name,
            "title": t.tour.title,
            "intro": t.tour.intro,
        }
        for t in _load_all_tours()
        if page.startswith(t.tour.entry_url)
    ]


@router.get("/{name}")
async def get_tour(
    name: str,
    _user: User = Depends(require_admin),
):
    for t in _load_all_tours():
        if t.name == name:
            return t.model_dump()
    raise HTTPException(status_code=404, detail="Tour not found")
