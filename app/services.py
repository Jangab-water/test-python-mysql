from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload
from . import models, schemas
from .auth import get_password_hash
import logging

logger = logging.getLogger(__name__)


# ============= User Services =============

async def get_user_by_username(db: AsyncSession, username: str):
    """Get user by username"""
    try:
        result = await db.execute(
            select(models.User).where(models.User.username == username)
        )
        return result.scalar_one_or_none()
    except SQLAlchemyError as e:
        logger.error(f"Error fetching user {username}: {str(e)}")
        raise


async def get_user(db: AsyncSession, user_id: int):
    """Get user by ID"""
    try:
        return await db.get(models.User, user_id)
    except SQLAlchemyError as e:
        logger.error(f"Error fetching user {user_id}: {str(e)}")
        raise


async def create_user(db: AsyncSession, user: schemas.UserCreate, is_admin: bool = False):
    """Create a new user"""
    try:
        # Check if username already exists
        existing_user = await get_user_by_username(db, user.username)
        if existing_user:
            raise ValueError("Username already exists")

        hashed_password = get_password_hash(user.password)
        db_user = models.User(
            username=user.username,
            hashed_password=hashed_password,
            is_admin=is_admin
        )
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)
        logger.info(f"Created user: {db_user.username} (admin: {is_admin})")
        return db_user
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Error creating user: {str(e)}")
        raise


# ============= Post Services =============

async def create_post(db: AsyncSession, post: schemas.PostCreate, author_id: int):
    """Create a new post"""
    try:
        db_post = models.Post(
            **post.model_dump(),
            author_id=author_id
        )
        db.add(db_post)
        await db.commit()
        await db.refresh(db_post)
        logger.info(f"Created post with id: {db_post.id} by user {author_id}")
        return db_post
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Error creating post: {str(e)}")
        raise


async def get_post(db: AsyncSession, post_id: int, include_deleted: bool = False):
    """Get post by ID"""
    try:
        query = select(models.Post).options(selectinload(models.Post.author)).where(models.Post.id == post_id)
        if not include_deleted:
            query = query.where(models.Post.is_deleted == False)

        result = await db.execute(query)
        return result.scalar_one_or_none()
    except SQLAlchemyError as e:
        logger.error(f"Error fetching post {post_id}: {str(e)}")
        raise


async def get_posts(db: AsyncSession, skip: int = 0, limit: int = 100, include_deleted: bool = False):
    """Get all posts"""
    try:
        query = select(models.Post).options(selectinload(models.Post.author)).offset(skip).limit(limit)
        if not include_deleted:
            query = query.where(models.Post.is_deleted == False)

        result = await db.execute(query)
        return result.scalars().all()
    except SQLAlchemyError as e:
        logger.error(f"Error fetching posts: {str(e)}")
        raise


async def update_post(db: AsyncSession, post_id: int, post: schemas.PostUpdate):
    """Update a post"""
    try:
        db_post = await get_post(db, post_id, include_deleted=False)
        if not db_post:
            return None

        update_data = post.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_post, key, value)

        db.add(db_post)
        await db.commit()
        await db.refresh(db_post)
        logger.info(f"Updated post with id: {post_id}")
        return db_post
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Error updating post {post_id}: {str(e)}")
        raise


async def soft_delete_post(db: AsyncSession, post_id: int):
    """Soft delete a post (mark as deleted)"""
    try:
        db_post = await get_post(db, post_id, include_deleted=False)
        if not db_post:
            return None

        db_post.is_deleted = True
        db.add(db_post)
        await db.commit()
        await db.refresh(db_post)
        logger.info(f"Soft deleted post with id: {post_id}")
        return db_post
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Error soft deleting post {post_id}: {str(e)}")
        raise


async def hard_delete_post(db: AsyncSession, post_id: int):
    """Hard delete a post (actually remove from database) - admin only"""
    try:
        db_post = await get_post(db, post_id, include_deleted=True)
        if not db_post:
            return None

        await db.delete(db_post)
        await db.commit()
        logger.info(f"Hard deleted post with id: {post_id}")
        return db_post
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Error hard deleting post {post_id}: {str(e)}")
        raise
