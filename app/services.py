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
    logger.debug(f"[SERVICE] get_user_by_username: {username}")
    try:
        result = await db.execute(
            select(models.User).where(models.User.username == username)
        )
        user = result.scalar_one_or_none()
        logger.debug(f"[SERVICE] User found: {user.username if user else 'None'}")
        return user
    except SQLAlchemyError as e:
        logger.error(f"[SERVICE] Error fetching user {username}: {str(e)}")
        raise


async def get_user(db: AsyncSession, user_id: int):
    """Get user by ID"""
    logger.debug(f"[SERVICE] get_user: id={user_id}")
    try:
        user = await db.get(models.User, user_id)
        logger.debug(f"[SERVICE] User found: {user.username if user else 'None'}")
        return user
    except SQLAlchemyError as e:
        logger.error(f"[SERVICE] Error fetching user {user_id}: {str(e)}")
        raise


async def create_user(db: AsyncSession, user: schemas.UserCreate, is_admin: bool = False):
    """Create a new user"""
    logger.debug(f"[SERVICE] create_user: {user.username}, is_admin={is_admin}")
    try:
        # Check if username already exists
        existing_user = await get_user_by_username(db, user.username)
        if existing_user:
            logger.warning(f"[SERVICE] Username already exists: {user.username}")
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
        logger.info(f"[SERVICE] User created: {db_user.username} (admin: {is_admin})")
        return db_user
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"[SERVICE] Error creating user: {str(e)}")
        raise


# ============= Post Services =============

async def create_post(db: AsyncSession, post: schemas.PostCreate, author_id: int):
    """Create a new post"""
    logger.debug(f"[SERVICE] create_post: author_id={author_id}, title={post.title[:30]}")
    try:
        db_post = models.Post(
            **post.model_dump(),
            author_id=author_id
        )
        db.add(db_post)
        await db.commit()
        await db.refresh(db_post)
        logger.info(f"[SERVICE] Post created: id={db_post.id}, author_id={author_id}")
        return db_post
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"[SERVICE] Error creating post: {str(e)}")
        raise


async def get_post(db: AsyncSession, post_id: int, include_deleted: bool = False):
    """Get post by ID"""
    logger.debug(f"[SERVICE] get_post: id={post_id}, include_deleted={include_deleted}")
    try:
        query = select(models.Post).options(selectinload(models.Post.author)).where(models.Post.id == post_id)
        if not include_deleted:
            query = query.where(models.Post.is_deleted == False)

        result = await db.execute(query)
        post = result.scalar_one_or_none()
        logger.debug(f"[SERVICE] Post found: {post.id if post else 'None'}")
        return post
    except SQLAlchemyError as e:
        logger.error(f"[SERVICE] Error fetching post {post_id}: {str(e)}")
        raise


async def get_posts(db: AsyncSession, skip: int = 0, limit: int = 100, include_deleted: bool = False):
    """Get all posts"""
    logger.debug(f"[SERVICE] get_posts: skip={skip}, limit={limit}, include_deleted={include_deleted}")
    try:
        query = select(models.Post).options(selectinload(models.Post.author)).offset(skip).limit(limit)
        if not include_deleted:
            query = query.where(models.Post.is_deleted == False)

        result = await db.execute(query)
        posts = result.scalars().all()
        logger.debug(f"[SERVICE] Retrieved {len(posts)} posts")
        return posts
    except SQLAlchemyError as e:
        logger.error(f"[SERVICE] Error fetching posts: {str(e)}")
        raise


async def update_post(db: AsyncSession, post_id: int, post: schemas.PostUpdate):
    """Update a post"""
    logger.debug(f"[SERVICE] update_post: id={post_id}")
    try:
        db_post = await get_post(db, post_id, include_deleted=False)
        if not db_post:
            logger.warning(f"[SERVICE] Post not found for update: id={post_id}")
            return None

        update_data = post.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_post, key, value)

        db.add(db_post)
        await db.commit()
        await db.refresh(db_post)
        logger.info(f"[SERVICE] Post updated: id={post_id}")
        return db_post
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"[SERVICE] Error updating post {post_id}: {str(e)}")
        raise


async def soft_delete_post(db: AsyncSession, post_id: int):
    """Soft delete a post (mark as deleted)"""
    logger.debug(f"[SERVICE] soft_delete_post: id={post_id}")
    try:
        db_post = await get_post(db, post_id, include_deleted=False)
        if not db_post:
            logger.warning(f"[SERVICE] Post not found for soft delete: id={post_id}")
            return None

        db_post.is_deleted = True
        db.add(db_post)
        await db.commit()
        await db.refresh(db_post)
        logger.info(f"[SERVICE] Post soft deleted: id={post_id}")
        return db_post
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"[SERVICE] Error soft deleting post {post_id}: {str(e)}")
        raise


async def hard_delete_post(db: AsyncSession, post_id: int):
    """Hard delete a post (actually remove from database) - admin only"""
    logger.debug(f"[SERVICE] hard_delete_post: id={post_id}")
    try:
        db_post = await get_post(db, post_id, include_deleted=True)
        if not db_post:
            logger.warning(f"[SERVICE] Post not found for hard delete: id={post_id}")
            return None

        await db.delete(db_post)
        await db.commit()
        logger.info(f"[SERVICE] Post hard deleted: id={post_id}")
        return db_post
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"[SERVICE] Error hard deleting post {post_id}: {str(e)}")
        raise
