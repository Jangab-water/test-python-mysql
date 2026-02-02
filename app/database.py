from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get database URL from environment variable
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+aiomysql://root:Mysql8#@localhost/dbmod"  # fallback for development
)

# Get echo setting from environment
DB_ECHO = os.getenv("DB_ECHO", "true").lower() == "true"

async_engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=DB_ECHO,
    pool_pre_ping=True,  # verify connections before using them
    pool_size=5,
    max_overflow=10
)

AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
