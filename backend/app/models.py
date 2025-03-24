from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class ChatRequest(BaseModel):
    """
    Request model for chat endpoint
    """
    message: str = Field(..., description="The message sent by the user")
    visitor_id: str = Field(..., description="Unique identifier for the visitor")
    visitor_name: Optional[str] = Field(None, description="Optional name for the visitor")
    target_user_id: Optional[str] = Field(None, description="Optional target user ID for user-specific chatbots")


class ChatResponse(BaseModel):
    """
    Response model for chat endpoint
    """
    response: str = Field(..., description="The response from the AI assistant")
    query_time_ms: float = Field(..., description="Time taken to process the query in milliseconds")


class ChatHistoryItem(BaseModel):
    """
    Model for a single chat history item
    """
    id: str
    message: str
    sender: str
    response: Optional[str] = None
    visitor_id: str
    visitor_name: Optional[str] = None
    target_user_id: Optional[str] = None
    timestamp: str


class ChatHistoryResponse(BaseModel):
    """
    Response model for chat history endpoint
    """
    history: List[ChatHistoryItem] = Field(default_factory=list)
    count: int


class ProfileData(BaseModel):
    """
    Model for profile data
    """
    id: Optional[str] = None
    user_id: Optional[str] = None
    name: Optional[str] = Field(None, description="User's name")
    location: Optional[str] = Field(None, description="User's location")
    bio: str
    skills: str
    experience: str
    projects: str
    interests: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AdminLoginRequest(BaseModel):
    """
    Request model for admin login
    """
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    """
    Response model for admin login
    """
    success: bool
    token: Optional[str] = None
    message: Optional[str] = None


class AdminCreateRequest(BaseModel):
    """
    Request model for creating an admin user
    """
    email: str = Field(..., description="Admin user email")
    password: str = Field(..., description="Admin user password")
    signup_code: str = Field(..., description="Signup code for authorization")


class AdminCreateResponse(BaseModel):
    """
    Response model for admin user creation
    """
    success: bool
    message: Optional[str] = None
    user_id: Optional[str] = None


class AdminInfoResponse(BaseModel):
    """
    Response model for admin user info
    """
    id: str
    email: str
    success: bool


class ErrorResponse(BaseModel):
    """
    Standard error response
    """
    error: str
    detail: Optional[str] = None 