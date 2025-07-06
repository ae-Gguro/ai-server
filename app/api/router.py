from fastapi import APIRouter
from app.api.endpoints import conversation, quiz, roleplay, utility

api_router = APIRouter()

api_router.include_router(conversation.router, prefix="/conversation", tags=["Conversation"])
api_router.include_router(quiz.router, prefix="/quiz", tags=["Quiz"])
api_router.include_router(roleplay.router, prefix="/roleplay", tags=["RolePlay"])

api_router.include_router(utility.router, tags=["Utility"])