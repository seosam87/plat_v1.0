from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.jwt import create_access_token
from app.auth.password import verify_password
from app.dependencies import get_db
from app.models.user import User
from app.services.audit_service import log_action
from app.services.user_service import get_user_by_email

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class UserOut(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool


@router.post("/token", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    user = await get_user_by_email(db, form_data.username)
    if not user or not verify_password(form_data.password, user.password_hash):
        await log_action(db, action="user.login_failed", detail={"email": form_data.username})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account deactivated")
    await log_action(db, action="user.login", user_id=user.id, entity_type="user", entity_id=str(user.id))
    token = create_access_token(str(user.id), user.role.value)
    return TokenResponse(access_token=token, token_type="bearer")


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut(
        id=str(current_user.id),
        username=current_user.username,
        email=current_user.email,
        role=current_user.role.value,
        is_active=current_user.is_active,
    )
