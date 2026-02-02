from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app import schemas, services, models
from app.database import get_db
from app.auth import get_current_active_user, require_admin

router = APIRouter(prefix="/posts", tags=["posts"])


@router.post("/", response_model=schemas.Post, status_code=status.HTTP_201_CREATED)
async def create_post(
    post: schemas.PostCreate,
    current_user: models.User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new post (requires authentication)"""
    return await services.create_post(db, post, current_user.id)


@router.get("/", response_model=list[schemas.PostWithAuthor])
async def read_posts(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Get all posts (non-deleted for regular users, all for admin)"""
    include_deleted = current_user.is_admin
    return await services.get_posts(db, skip, limit, include_deleted=include_deleted)


@router.get("/{post_id}", response_model=schemas.PostWithAuthor)
async def read_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Get a specific post"""
    include_deleted = current_user.is_admin
    db_post = await services.get_post(db, post_id, include_deleted=include_deleted)
    if not db_post:
        raise HTTPException(status_code=404, detail="Post not found")
    return db_post


@router.put("/{post_id}", response_model=schemas.Post)
async def update_post(
    post_id: int,
    post: schemas.PostUpdate,
    current_user: models.User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a post (author or admin only)"""
    db_post = await services.get_post(db, post_id, include_deleted=False)
    if not db_post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Check if user is author or admin
    if db_post.author_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this post"
        )

    updated_post = await services.update_post(db, post_id, post)
    return updated_post


@router.delete("/{post_id}", response_model=schemas.Post)
async def delete_post(
    post_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a post (soft delete for regular users, author or admin only)"""
    db_post = await services.get_post(db, post_id, include_deleted=False)
    if not db_post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Check if user is author or admin
    if db_post.author_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this post"
        )

    deleted_post = await services.soft_delete_post(db, post_id)
    return deleted_post


@router.delete("/{post_id}/hard", response_model=schemas.Post)
async def hard_delete_post(
    post_id: int,
    current_user: models.User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Permanently delete a post from database (admin only)"""
    db_post = await services.hard_delete_post(db, post_id)
    if not db_post:
        raise HTTPException(status_code=404, detail="Post not found")
    return db_post
