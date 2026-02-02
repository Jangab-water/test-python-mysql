from fastapi import APIRouter, Depends, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta

from app import schemas, services, models
from app.database import get_db
from app.auth import (
    verify_password,
    create_access_token,
    get_current_user_optional,
    get_current_user_from_cookie,
    set_auth_cookie,
    delete_auth_cookie,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

router = APIRouter(tags=["views"])
templates = Jinja2Templates(directory="templates")


# Helper function to add common context
async def get_template_context(request: Request, db: AsyncSession) -> dict:
    """Get common template context (user, flash messages, etc.)"""
    user = await get_current_user_optional(request, db)
    return {
        "request": request,
        "user": user,
        "is_authenticated": user is not None,
        "is_admin": user.is_admin if user else False
    }


# ============= Public Pages =============

@router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: AsyncSession = Depends(get_db)):
    """Home/Landing page"""
    context = await get_template_context(request, db)
    return templates.TemplateResponse("home.html", context)


# ============= Auth Pages =============

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Login page"""
    context = await get_template_context(request, db)
    # Redirect to posts if already logged in
    if context["is_authenticated"]:
        return RedirectResponse(url="/posts", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("auth/login.html", context)


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Handle login form submission"""
    user = await services.get_user_by_username(db, username)
    if not user or not verify_password(password, user.hashed_password):
        context = await get_template_context(request, db)
        context["error"] = "Incorrect username or password"
        context["username"] = username
        return templates.TemplateResponse("auth/login.html", context)

    # Create JWT token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires
    )

    # Set cookie and redirect
    response = RedirectResponse(url="/posts", status_code=status.HTTP_302_FOUND)
    set_auth_cookie(response, access_token)
    return response


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Register page"""
    context = await get_template_context(request, db)
    # Redirect to posts if already logged in
    if context["is_authenticated"]:
        return RedirectResponse(url="/posts", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("auth/register.html", context)


@router.post("/register")
async def register_submit(
    request: Request,
    username: str = Form(..., min_length=3, max_length=50),
    password: str = Form(..., min_length=4, max_length=100),
    password_confirm: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Handle registration form submission"""
    context = await get_template_context(request, db)
    context["username"] = username

    # Validate passwords match
    if password != password_confirm:
        context["error"] = "Passwords do not match"
        return templates.TemplateResponse("auth/register.html", context)

    # Try to create user
    try:
        user_data = schemas.UserCreate(username=username, password=password)
        await services.create_user(db, user_data, is_admin=False)

        # Auto-login after registration
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": username},
            expires_delta=access_token_expires
        )

        response = RedirectResponse(url="/posts", status_code=status.HTTP_302_FOUND)
        set_auth_cookie(response, access_token)
        return response

    except ValueError as e:
        context["error"] = str(e)
        return templates.TemplateResponse("auth/register.html", context)


@router.get("/logout")
async def logout(request: Request):
    """Logout (delete cookie)"""
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    delete_auth_cookie(response)
    return response


# ============= Post Pages =============

@router.get("/posts", response_class=HTMLResponse)
async def posts_list(
    request: Request,
    page: int = 1,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user_from_cookie)
):
    """Post list page with pagination"""
    limit = 10
    skip = (page - 1) * limit

    include_deleted = current_user.is_admin
    posts = await services.get_posts(db, skip=skip, limit=limit + 1, include_deleted=include_deleted)

    # Check if there's a next page
    has_next = len(posts) > limit
    posts = posts[:limit]

    context = await get_template_context(request, db)
    context.update({
        "posts": posts,
        "page": page,
        "has_next": has_next,
        "has_prev": page > 1
    })
    return templates.TemplateResponse("posts/list.html", context)


@router.get("/posts/new", response_class=HTMLResponse)
async def post_create_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user_from_cookie)
):
    """Create post page"""
    context = await get_template_context(request, db)
    context["action"] = "create"
    return templates.TemplateResponse("posts/form.html", context)


@router.post("/posts/new")
async def post_create_submit(
    request: Request,
    title: str = Form(..., min_length=1, max_length=255),
    content: str = Form(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user_from_cookie)
):
    """Handle create post form submission"""
    post_data = schemas.PostCreate(title=title, content=content)
    post = await services.create_post(db, post_data, current_user.id)

    return RedirectResponse(
        url=f"/posts/{post.id}",
        status_code=status.HTTP_302_FOUND
    )


@router.get("/posts/{post_id}", response_class=HTMLResponse)
async def post_detail(
    request: Request,
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user_from_cookie)
):
    """Post detail page"""
    include_deleted = current_user.is_admin
    post = await services.get_post(db, post_id, include_deleted=include_deleted)

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Check permissions
    can_edit = current_user.id == post.author_id or current_user.is_admin
    can_delete = current_user.id == post.author_id or current_user.is_admin

    context = await get_template_context(request, db)
    context.update({
        "post": post,
        "can_edit": can_edit,
        "can_delete": can_delete
    })
    return templates.TemplateResponse("posts/detail.html", context)


@router.get("/posts/{post_id}/edit", response_class=HTMLResponse)
async def post_edit_page(
    request: Request,
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user_from_cookie)
):
    """Edit post page"""
    post = await services.get_post(db, post_id, include_deleted=False)

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Check authorization
    if post.author_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    context = await get_template_context(request, db)
    context.update({
        "post": post,
        "action": "edit"
    })
    return templates.TemplateResponse("posts/form.html", context)


@router.post("/posts/{post_id}/edit")
async def post_edit_submit(
    request: Request,
    post_id: int,
    title: str = Form(..., min_length=1, max_length=255),
    content: str = Form(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user_from_cookie)
):
    """Handle edit post form submission"""
    post = await services.get_post(db, post_id, include_deleted=False)

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Check authorization
    if post.author_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    post_data = schemas.PostUpdate(title=title, content=content)
    await services.update_post(db, post_id, post_data)

    return RedirectResponse(
        url=f"/posts/{post_id}",
        status_code=status.HTTP_302_FOUND
    )


@router.post("/posts/{post_id}/delete")
async def post_delete_submit(
    request: Request,
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user_from_cookie)
):
    """Handle post deletion"""
    post = await services.get_post(db, post_id, include_deleted=False)

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Check authorization
    if post.author_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    await services.soft_delete_post(db, post_id)

    return RedirectResponse(url="/posts", status_code=status.HTTP_302_FOUND)


# ============= User Profile Page =============

@router.get("/profile", response_class=HTMLResponse)
async def profile_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user_from_cookie)
):
    """User profile/dashboard page"""
    # Get user's posts
    include_deleted = current_user.is_admin
    all_posts = await services.get_posts(db, skip=0, limit=1000, include_deleted=include_deleted)
    user_posts = [post for post in all_posts if post.author_id == current_user.id]

    context = await get_template_context(request, db)
    context.update({
        "user_posts": user_posts,
        "total_posts": len(user_posts)
    })
    return templates.TemplateResponse("profile.html", context)
