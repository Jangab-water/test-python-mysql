from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
import os
import logging

from . import schemas, models
from .database import get_db

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# JWT settings
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    # Bcrypt has a 72 byte limit, truncate if necessary
    password_bytes = plain_password.encode('utf-8')[:72]
    return pwd_context.verify(password_bytes, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    # Bcrypt has a 72 byte limit, truncate if necessary
    password_bytes = password.encode('utf-8')[:72]
    return pwd_context.hash(password_bytes)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> models.User:
    """Get current authenticated user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = schemas.TokenData(username=username)
    except JWTError:
        raise credentials_exception

    from .services import get_user_by_username
    user = await get_user_by_username(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: models.User = Depends(get_current_user)
) -> models.User:
    """Get current active user"""
    return current_user


def require_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    """Require admin privileges"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


# ============= Cookie-based Authentication for HTML Views =============

COOKIE_NAME = "access_token"
COOKIE_MAX_AGE = ACCESS_TOKEN_EXPIRE_MINUTES * 60  # Convert to seconds


def set_auth_cookie(response: Response, token: str):
    """Set JWT token in httpOnly cookie"""
    response.set_cookie(
        key=COOKIE_NAME,
        value=f"Bearer {token}",
        max_age=COOKIE_MAX_AGE,
        path="/",  # Cookie available for all paths
        httponly=True,  # Prevent JavaScript access
        secure=False,  # Set to True in production with HTTPS
        samesite="lax"  # CSRF protection
    )


def delete_auth_cookie(response: Response):
    """Delete auth cookie (logout)"""
    response.delete_cookie(key=COOKIE_NAME, path="/")


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Optional[models.User]:
    """Get current user from cookie or return None"""
    token = request.cookies.get(COOKIE_NAME)
    logger.info(f"[AUTH] Path: {request.url.path}, Method: {request.method}")
    logger.info(f"[AUTH] Cookie token exists: {token is not None}")

    if not token:
        logger.warning("[AUTH] No token in cookie")
        return None

    # Remove "Bearer " prefix if present
    if token.startswith("Bearer "):
        token = token[7:]

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            logger.warning("[AUTH] No username in token payload")
            return None

        from .services import get_user_by_username
        user = await get_user_by_username(db, username=username)
        logger.info(f"[AUTH] User found: {user.username if user else 'None'}")
        return user
    except JWTError as e:
        logger.error(f"[AUTH] JWT decode error: {e}")
        return None


class RequireLoginException(Exception):
    """Exception to trigger login redirect"""
    pass


async def get_current_user_from_cookie(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> models.User:
    """Get current user from cookie or redirect to login"""
    user = await get_current_user_optional(request, db)
    if user is None:
        raise RequireLoginException()
    return user
