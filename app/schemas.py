from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


# User Schemas
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="User ID")


class UserCreate(UserBase):
    password: str = Field(..., min_length=4, max_length=100, description="Password")


class UserLogin(BaseModel):
    username: str = Field(..., description="User ID")
    password: str = Field(..., description="Password")


class User(UserBase):
    id: int
    is_admin: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class UserInDB(User):
    hashed_password: str


# Post Schemas
class PostBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Post title")
    content: str = Field(..., min_length=1, description="Post content")


class PostCreate(PostBase):
    pass


class PostUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255, description="Post title")
    content: Optional[str] = Field(None, min_length=1, description="Post content")


class Post(PostBase):
    id: int
    author_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_deleted: bool
    model_config = ConfigDict(from_attributes=True)


class PostWithAuthor(Post):
    author: User


# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None
