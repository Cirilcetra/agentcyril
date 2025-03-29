from fastapi import FastAPI, Request, Depends, HTTPException, File, UploadFile, Form, Body, BackgroundTasks, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Union
import logging
import os
import json
import uuid
from app import models
from app.database import get_profile_data, update_profile_data, log_chat_message, get_chat_history, get_or_create_chatbot
from app.embeddings import add_profile_to_vector_db, query_vector_db, generate_ai_response, add_conversation_to_vector_db
from app.routes import chatbot, profiles, admin
import time
import openai
from dotenv import load_dotenv
from app.auth import get_current_user, User
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, FileResponse, JSONResponse
import re
import jwt
from fastapi.staticfiles import StaticFiles
from app.routes import chatbot as chatbot_routes
from app.routes import documents

# EMERGENCY FIX - Import the emergency endpoint
try:
    from app.bypass_auth import emergency_chat_endpoint, ChatResponse
    EMERGENCY_MODE = True
    logging.info("🚨 EMERGENCY MODE ENABLED: Using authentication bypass")
except ImportError:
    EMERGENCY_MODE = False
    logging.warning("❌ Emergency mode not available")

try:
    from app.routes import auth
except ImportError:
    logging.warning("Auth routes not imported. Make sure app/routes/auth.py exists.")

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("backend.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configure OpenAI
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("Missing OpenAI API key. Set OPENAI_API_KEY in .env file.")

try:
    # Initialize OpenAI client
    openai.api_key = openai_api_key
    # Test the API key with a simple request
    openai.models.list()
    logger.info("Successfully initialized OpenAI client")
except Exception as e:
    logger.error(f"Error initializing OpenAI client: {str(e)}")
    if "invalid_api_key" in str(e).lower():
        logger.error("Invalid API key format detected. Please check your OpenAI API key format.")
    raise

# Create the FastAPI app
app = FastAPI()

# Authentication middleware
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Public paths that don't require authentication
        public_paths = [
            r"^/$",                      # Root path
            r"^/docs",                   # Swagger documentation
            r"^/redoc",                  # ReDoc
            r"^/openapi.json",           # OpenAPI schema
            r"^/profile",                # TEMP: Make profile endpoint public for testing
            r"^/chat/public",            # Public chat endpoints
            r"^/chat/[^/]+/public$",     # Public chatbot endpoint for specific user (GET and POST)
            r"^/chat/[^/]+/public/history", # Public chat history endpoint
            r"^/profile/public",         # Public profile endpoints
            r"^/emergency-chat",         # Emergency chat endpoint
            r"^/check-chat",             # Chat status check
            r"^/chat$",                  # Main chat endpoint
            r"^/chat/history",           # Chat history endpoint
        ]
        
        # Check if the current path is in the public paths
        path = request.url.path
        for pattern in public_paths:
            if re.match(pattern, path):
                return await call_next(request)
        
        # If path requires authentication, check for Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return Response(
                status_code=401,
                content=json.dumps({"detail": "Not authenticated"}),
                media_type="application/json"
            )
        
        # Continue with the request
        return await call_next(request)

# Add middleware
app.add_middleware(AuthMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Include routers from the routes directory
app.include_router(chatbot.router, prefix="/chat", tags=["chatbot"])
app.include_router(profiles.router, prefix="/profile", tags=["profiles"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(documents.router, prefix="/documents", tags=["documents"])
try:
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
except NameError:
    logging.warning("Auth router not included. Authentication endpoints will not be available.")

# Add the chatbot routes
app.include_router(chatbot_routes.router)

# Define models
class ProfileData(BaseModel):
    bio: Optional[str] = None
    skills: Optional[str] = None
    experience: Optional[str] = None
    projects: Optional[str] = None
    interests: Optional[str] = None
    name: Optional[str] = None
    location: Optional[str] = None
    user_id: Optional[str] = None  # Add user_id field for Supabase
    calendly_link: Optional[str] = None  # Calendly meeting scheduling link
    meeting_rules: Optional[str] = None  # Rules for allowing meeting requests

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    user_id: Optional[str] = None  # Kept for API compatibility but not used
    visitor_id: Optional[str] = None
    visitor_name: Optional[str] = None
    chatbot_id: Optional[str] = None

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to the AIChat API"}

# Get profile data - kept for backward compatibility
@app.get("/profile")
async def profile(user_id: Optional[str] = None, request: Request = None):
    """Get profile data"""
    try:
        # Try to extract JWT from request
        effective_user_id = user_id
        if request and request.headers.get("Authorization"):
            auth_header = request.headers.get("Authorization")
            token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else None
            
            if token:
                try:
                    # Decode JWT to get user ID
                    payload = jwt.decode(token, options={"verify_signature": False})
                    jwt_user_id = payload.get("sub")
                    if jwt_user_id:
                        logging.info(f"Extracted user_id from JWT: {jwt_user_id}")
                        effective_user_id = jwt_user_id
                except Exception as jwt_error:
                    logging.warning(f"Error decoding JWT: {jwt_error}")
        
        logging.info(f"Getting profile data for user_id: {effective_user_id}")
        profile_data = get_profile_data(user_id=effective_user_id)
        return profile_data
    except Exception as e:
        logging.error(f"Error getting profile data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Update profile data (POST endpoint) - kept for backward compatibility
@app.post("/profile")
async def update_profile_post(profile_data: ProfileData, user_id: Optional[str] = None, request: Request = None):
    """Update profile data using POST"""
    return await update_profile_handler(profile_data, user_id, request)

# Update profile data (PUT endpoint for compatibility) - kept for backward compatibility
@app.put("/profile")
async def update_profile_put(profile_data: ProfileData, user_id: Optional[str] = None, request: Request = None):
    """Update profile data using PUT (for compatibility)"""
    return await update_profile_handler(profile_data, user_id, request)

# Shared handler for profile updates
async def update_profile_handler(profile_data: ProfileData, user_id: Optional[str] = None, request: Request = None):
    """Shared handler for profile updates"""
    try:
        # Try to extract JWT from request
        effective_user_id = user_id
        if request and request.headers.get("Authorization"):
            auth_header = request.headers.get("Authorization")
            token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else None
            
            if token:
                try:
                    # Decode JWT to get user ID
                    payload = jwt.decode(token, options={"verify_signature": False})
                    jwt_user_id = payload.get("sub")
                    if jwt_user_id:
                        logging.info(f"Extracted user_id from JWT: {jwt_user_id}")
                        effective_user_id = jwt_user_id
                except Exception as jwt_error:
                    logging.warning(f"Error decoding JWT: {jwt_error}")
        
        logging.info(f"Updating profile data for user_id: {effective_user_id}")
        
        # Convert Pydantic model to dict
        profile_dict = profile_data.dict(exclude_unset=True)
        
        # Log data for debugging
        logging.info(f"Profile data received: {profile_dict}")
        logging.info(f"User ID from query param: {user_id}")
        logging.info(f"User ID from profile data: {profile_dict.get('user_id')}")
        
        # Check for user_id in profile_data, fall back to extracted JWT user_id or query param if not provided
        profile_user_id = profile_dict.get('user_id')
        final_user_id = profile_user_id or effective_user_id
        
        if final_user_id:
            logging.info(f"Using final user_id: {final_user_id}")
            # Ensure the user_id is also in the profile data
            profile_dict['user_id'] = final_user_id
        
        # Update profile data in the database
        updated_profile = update_profile_data(profile_dict, final_user_id)
        
        if not updated_profile:
            logging.error("Failed to update profile data")
            raise HTTPException(status_code=500, detail="Failed to update profile data")
        
        # Add profile data to vector database
        add_profile_to_vector_db(updated_profile)
        
        return {"message": "Profile updated successfully", "profile": updated_profile}
    except Exception as e:
        logging.error(f"Error updating profile data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Helper function to check if meeting request is valid based on rules
def is_valid_meeting_request(message: str, meeting_rules: str) -> bool:
    """
    Check if a meeting request is valid based on the configured rules
    """
    if not meeting_rules:
        return True  # If no rules are set, allow all meeting requests
        
    # Convert message and rules to lowercase for case-insensitive matching
    message = message.lower()
    rules = meeting_rules.lower()
    
    # Common meeting request keywords
    meeting_keywords = ["meet", "meeting", "schedule", "appointment", "chat", "discuss", "call"]
    
    # Check if this is actually a meeting request
    is_meeting_request = any(keyword in message for keyword in meeting_keywords)
    if not is_meeting_request:
        return False
        
    # Extract purposes mentioned in the rules
    # Example rule: "Only allow meetings for: project discussions, job opportunities, consulting"
    allowed_purposes = [purpose.strip() for purpose in rules.split(",")]
    
    # Check if any of the allowed purposes are mentioned in the message
    return any(purpose in message for purpose in allowed_purposes)

# Update the chat function to handle meeting requests
@app.post("/chat")
async def chat(chat_request: models.ChatRequest):
    try:
        # Get the latest user message
        user_message = chat_request.messages[-1].content.lower() if chat_request.messages else ""
        
        # Check if this might be a meeting request
        if any(keyword in user_message for keyword in ["meet", "meeting", "schedule", "appointment", "chat", "discuss", "call"]):
            # Get the profile data to check meeting rules and Calendly link
            profile_data = None
            if chat_request.user_id:
                profile_data = get_profile_data(user_id=chat_request.user_id)
            
            if profile_data and profile_data.get("calendly_link"):
                # Check if the meeting request is valid based on rules
                if is_valid_meeting_request(user_message, profile_data.get("meeting_rules", "")):
                    calendly_link = profile_data["calendly_link"]
                    meeting_response = (
                        f"I'd be happy to help you schedule a meeting! You can use my Calendly link to find a suitable time: "
                        f"{calendly_link}\n\nPlease select a time that works best for you."
                    )
                    return {"response": meeting_response}
                else:
                    return {"response": "I understand you'd like to schedule a meeting. However, based on our meeting policy, "
                                      "I can only schedule meetings for specific purposes. Could you please clarify the purpose "
                                      "of the meeting?"}
        
        # If not a meeting request or no Calendly link set, proceed with normal chat handling
        logging.info(f"Processing chat message")
        
        # Extract visitor information
        visitor_id = chat_request.visitor_id
        visitor_name = chat_request.visitor_name
        target_user_id = chat_request.target_user_id
        chatbot_id = chat_request.chatbot_id
        
        logging.info(f"Chat request from visitor: {visitor_id}, name: {visitor_name}, user_id: {target_user_id}, chatbot_id: {chatbot_id}")
        
        # Get the message directly from the request
        message = chat_request.message
        
        if not message or message.strip() == "":
            logging.warning("No valid user message found in request")
            return {"response": "I didn't receive a valid message. Please try again."}
        
        logging.info(f"User message: {message[:50]}...")
        
        # Get chatbot and profile data
        chatbot = None
        owner_user_id = target_user_id
        
        if chatbot_id:
            # If a specific chatbot ID is provided, use it
            chatbot = get_or_create_chatbot(chatbot_id=chatbot_id)
            if chatbot:
                owner_user_id = chatbot.get("user_id")
                logging.info(f"Using chatbot with ID {chatbot_id}, owned by user {owner_user_id}")
        elif target_user_id:
            # If a target user ID is provided but no chatbot ID, get/create the user's default chatbot
            chatbot = get_or_create_chatbot(user_id=target_user_id)
            logging.info(f"Using default chatbot for user {target_user_id}")
        
        # Get profile data for the appropriate user
        profile_data = get_profile_data(user_id=owner_user_id)
        logging.info(f"Retrieved profile data: {profile_data.get('id', 'No ID')}") 
        
        # Query vector database for relevant information including conversation history
        logging.info(f"Querying vector DB for relevant context and conversation history for user {owner_user_id}")
        search_results = query_vector_db(
            query=message, 
            n_results=3,
            user_id=owner_user_id,  # Use the chatbot owner's user_id
            visitor_id=visitor_id,
            include_conversation=True
        )
        
        # Get sequential conversation history for UI/display context
        logging.info(f"Getting sequential conversation history for visitor: {visitor_id}")
        history_limit = 10  # Get last 10 messages (5 exchanges)
        chat_history = get_chat_history(
            limit=history_limit,
            visitor_id=visitor_id,
            target_user_id=owner_user_id,
            chatbot_id=chatbot.get("id") if chatbot else None
        )
        
        # Sort history to have oldest messages first
        if chat_history:
            chat_history = sorted(
                chat_history,
                key=lambda x: x.get("timestamp", ""),
                reverse=False  # Oldest messages first
            )
            logging.info(f"Found {len(chat_history)} previous messages in conversation history")
        else:
            logging.info("No previous conversation history found")
            chat_history = []
        
        # Generate AI response using the embeddings.py implementation
        ai_response = generate_ai_response(
            message=message,  # Using the message as the query
            search_results=search_results,
            profile_data=profile_data,
            chat_history=chat_history
        )
        
        logging.info(f"Generated AI response: {ai_response[:50]}...")
        
        # Log chat interaction
        logging.info("Saving chat message to database...")
        chat_log_result = log_chat_message(
            message=message,
            sender="user", 
            response=ai_response,
            visitor_id=chat_request.visitor_id,
            visitor_name=chat_request.visitor_name,
            target_user_id=owner_user_id,
            chatbot_id=chatbot.get("id") if chatbot else None
        )
        
        # Also store the conversation in the vector database for semantic search
        message_id = chat_log_result[0]["id"] if chat_log_result and len(chat_log_result) > 0 else None
        logging.info(f"Adding conversation to vector database for future reference with user_id: {owner_user_id}")
        add_conversation_to_vector_db(
            message=message,
            response=ai_response,
            visitor_id=visitor_id,
            message_id=message_id,
            user_id=owner_user_id  # Pass the chatbot owner's user_id
        )
        
        logging.info(f"Chat message saved: {chat_log_result is not None}")
        
        return {"response": ai_response}
    except Exception as e:
        logging.error(f"Error processing chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Get chat history endpoint - kept for backward compatibility
@app.get("/chat/history")
async def history(visitor_id: Optional[str] = None, target_user_id: Optional[str] = None, limit: int = 50):
    """Get chat history"""
    try:
        logging.info(f"Getting chat history for visitor: {visitor_id}, target: {target_user_id}, limit: {limit}")
        
        # Get chat history
        history = get_chat_history(
            limit=limit,
            visitor_id=visitor_id,
            target_user_id=target_user_id
        )
        
        logging.info(f"Retrieved {len(history)} chat history entries")
        if len(history) > 0:
            logging.info(f"First message: {history[0].get('message', 'N/A')[:30]}...")
        else:
            logging.info("No chat history found")
        
        # Convert to ChatHistoryResponse format for better compatibility
        formatted_history = []
        for item in history:
            formatted_history.append(models.ChatHistoryItem(
                id=item["id"],
                message=item["message"],
                sender=item["sender"],
                response=item.get("response"),
                visitor_id=item["visitor_id"],
                visitor_name=item.get("visitor_name"),
                target_user_id=item.get("target_user_id"),
                timestamp=item["timestamp"]
            ))
        
        response = models.ChatHistoryResponse(
            history=formatted_history,
            count=len(formatted_history)
        )
        
        logging.info(f"Returning response with {len(formatted_history)} items, using ChatHistoryResponse format")
        return response
        
    except Exception as e:
        logging.error(f"Error getting chat history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Add a direct route for public chatbot access by user ID
@app.get("/chat/{user_id}/public")
async def get_public_chatbot_by_user_id(user_id: str):
    """
    Public endpoint to get or create a chatbot for a user
    This is accessible without authentication
    """
    try:
        # Get or create a chatbot for the user
        chatbot = get_or_create_chatbot(user_id=user_id)
        
        if not chatbot:
            raise HTTPException(
                status_code=404, 
                detail=f"No chatbot found for user {user_id}"
            )
        
        # Return the chatbot data
        return chatbot
    except Exception as e:
        logging.error(f"Error getting public chatbot by user ID: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get chatbot: {str(e)}"
        )

# Add a POST endpoint for public chatbot access by user ID
@app.post("/chat/{user_id}/public", response_model=models.ChatResponse)
async def chat_with_public_chatbot_by_user_id(user_id: str, request: models.ChatRequest):
    """
    Public endpoint to chat with a chatbot by user ID
    This is accessible without authentication
    """
    try:
        # Forward the request to the chatbot router handler
        from app.routes.chatbot import chat_with_public_chatbot
        return await chat_with_public_chatbot(user_id, request)
    except Exception as e:
        logging.error(f"Error in public chat endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process chat request: {str(e)}"
        )

# Add a GET endpoint for public chatbot history access by user ID
@app.get("/chat/{user_id}/public/history")
async def get_public_chatbot_history(user_id: str, visitor_id: Optional[str] = None, limit: int = 50):
    """
    Public endpoint to get chat history for a public chatbot by user ID
    This is accessible without authentication
    """
    try:
        # Get or create a chatbot for the user
        chatbot = get_or_create_chatbot(user_id=user_id)
        
        if not chatbot:
            raise HTTPException(
                status_code=404,
                detail=f"No chatbot found for user {user_id}"
            )
        
        # Get chat history for this chatbot and visitor
        logging.info(f"Getting public chat history for user_id: {user_id}, visitor_id: {visitor_id}, chatbot_id: {chatbot.get('id')}")
        history = get_chat_history(
            limit=limit,
            visitor_id=visitor_id,
            chatbot_id=chatbot.get("id")
        )
        
        logging.info(f"Retrieved {len(history)} chat history entries")
        
        # Convert to ChatHistoryResponse format
        formatted_history = []
        for item in history:
            formatted_history.append(models.ChatHistoryItem(
                id=item.get("id", ""),
                message=item.get("message", ""),
                sender=item.get("sender", "user"),
                response=item.get("response"),
                visitor_id=item.get("visitor_id", ""),
                visitor_name=item.get("visitor_name"),
                timestamp=item.get("created_at") or item.get("timestamp", "")
            ))
        
        response = models.ChatHistoryResponse(
            history=formatted_history,
            count=len(formatted_history)
        )
        
        logging.info(f"Returning public chat history with {len(formatted_history)} items")
        return response
        
    except Exception as e:
        logging.error(f"Error getting public chat history: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get chat history: {str(e)}"
        )

# Add the emergency chat endpoint
@app.post("/emergency-chat", response_model=ChatResponse)
async def emergency_chat(request: Request):
    # Parse the request body manually
    body = await request.json()
    # Pass the request to the emergency endpoint
    return await emergency_chat_endpoint(body)

# Add a check endpoint to verify chat functionality
@app.get("/check-chat")
async def check_chat():
    return {"status": "ok", "emergency_mode": EMERGENCY_MODE}

# Run the application with uvicorn
if __name__ == "__main__":
    import uvicorn
    import argparse
    
    parser = argparse.ArgumentParser(description="AIChat API Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind the server to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    uvicorn.run(
        "app.main:app", 
        host=args.host, 
        port=args.port, 
        reload=args.debug
    ) 