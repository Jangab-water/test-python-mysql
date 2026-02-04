from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta
import logging

from app import schemas, services
from app.database import get_db
from app.auth import (
    verify_password,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    get_current_active_user
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
async def register(
    user: schemas.UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user"""
    logger.debug(f"[API] POST /auth/register - username: {user.username}")
    try:
        db_user = await services.create_user(db, user, is_admin=False)
        logger.info(f"[API] User registered successfully: {user.username}")
        return db_user
    except ValueError as e:
        logger.warning(f"[API] Registration failed for {user.username}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/login", response_model=schemas.Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """Login and get access token"""
    logger.debug(f"[API] POST /auth/login - username: {form_data.username}")
    user = await services.get_user_by_username(db, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning(f"[API] Login failed for {form_data.username}: Invalid credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    logger.info(f"[API] User logged in: {user.username}")
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=schemas.User)
async def read_users_me(
    current_user: schemas.User = Depends(get_current_active_user)
):
    """Get current user information"""
    logger.debug(f"[API] GET /auth/me - user: {current_user.username}")
    return current_user
