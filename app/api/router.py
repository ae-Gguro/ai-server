from fastapi import APIRouter
from app.api.endpoints import conversation, quiz, roleplay, utility, history, analysis, chosung, chatroom, animal

api_router = APIRouter()

api_router.include_router(conversation.router, prefix="/api/conversation", tags=["Conversation"])
api_router.include_router(quiz.router, prefix="/api/quiz", tags=["Daily Quiz"])
api_router.include_router(roleplay.router, prefix="/api/roleplay", tags=["RolePlay"])

api_router.include_router(utility.router,  prefix="/api", tags=["Utility"])
api_router.include_router(history.router, prefix="/api/history", tags=["History"])
api_router.include_router(analysis.router, prefix="/api/analysis", tags=["Analysis"]) 
api_router.include_router(chosung.router, prefix="/api/chosung", tags=["Chosung Quiz"]) 
api_router.include_router(chatroom.router, prefix="/api/chatrooms", tags=["Chatrooms"])
api_router.include_router(animal.router, prefix="/api/animal-quiz", tags=["Animal Quiz"]) 
