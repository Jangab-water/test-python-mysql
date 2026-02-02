from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging

from app import models, schemas, services
from app.database import async_engine, AsyncSessionLocal
from app.routers import posts, auth

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def create_db_and_tables():
    """Create database tables"""
    async with async_engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
        logger.info("Database tables created successfully")


async def initialize_admin():
    """Initialize admin user if not exists"""
    async with AsyncSessionLocal() as db:
        try:
            admin_user = await services.get_user_by_username(db, "admin")
            if not admin_user:
                admin_data = schemas.UserCreate(username="admin", password="admin")
                await services.create_user(db, admin_data, is_admin=True)
                logger.info("Admin user created successfully (username: admin, password: admin)")
            else:
                logger.info("Admin user already exists")
        except Exception as e:
            logger.error(f"Error initializing admin user: {str(e)}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up application...")
    await create_db_and_tables()
    await initialize_admin()
    yield
    # Shutdown
    logger.info("Shutting down application...")
    await async_engine.dispose()


app = FastAPI(
    title="게시판 서비스 (Board Service)",
    description="FastAPI + SQLAlchemy 기반 게시판 서비스",
    version="1.0.0",
    lifespan=lifespan
)

# Include routers
app.include_router(auth.router)
app.include_router(posts.router)


@app.get("/")
async def root():
    return {
        "message": "게시판 서비스에 오신 것을 환영합니다!",
        "description": "FastAPI + SQLAlchemy (async MySQL) 기반 게시판",
        "endpoints": {
            "auth": "/auth (register, login, me)",
            "posts": "/posts (CRUD operations)",
            "docs": "/docs"
        }
    }
