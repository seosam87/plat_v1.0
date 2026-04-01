"""Invite link system for client onboarding."""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.auth.password import hash_password
from app.dependencies import get_db
from app.models.invite import InviteLink
from app.models.project import Project
from app.models.user import User, UserRole
from app.services.user_service import create_user

router = APIRouter(prefix="/invites", tags=["invites"])


@router.post("/projects/{project_id}")
async def create_invite(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Generate an invite link for a project (valid 7 days)."""
    project = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    token = uuid.uuid4().hex
    invite = InviteLink(
        project_id=project_id,
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(invite)
    await db.flush()
    await db.commit()
    return {"token": token, "expires_at": invite.expires_at.isoformat()}


class AcceptInviteRequest(BaseModel):
    token: str
    username: str
    email: str
    password: str


@router.post("/accept")
async def accept_invite(
    payload: AcceptInviteRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Accept an invite — creates a client account bound to the project."""
    invite = (await db.execute(
        select(InviteLink).where(InviteLink.token == payload.token)
    )).scalar_one_or_none()

    if not invite:
        raise HTTPException(status_code=404, detail="Invalid invite token")
    if invite.used:
        raise HTTPException(status_code=400, detail="Invite already used")
    if invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invite expired")

    # Create client user
    user = await create_user(
        db, payload.username, payload.email,
        hash_password(payload.password), UserRole.client,
    )

    # Bind to project
    project = (await db.execute(select(Project).where(Project.id == invite.project_id))).scalar_one()
    project.client_user_id = user.id

    invite.used = True
    await db.flush()
    await db.commit()

    return {"user_id": str(user.id), "project_id": str(project.id), "role": "client"}
