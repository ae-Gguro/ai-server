from fastapi import APIRouter, BackgroundTasks, Depends
from app.models.schemas import RolePlayStartRequest, ChatRequest
from app.services.chatbot_system import chatbot_system
from app.core.security import get_current_user_id 

router = APIRouter()

@router.post("/start", summary="역할놀이 시작")
async def start_roleplay(
    req: RolePlayStartRequest, 
    background_tasks: BackgroundTasks,
    profile_id: int = Depends(get_current_user_id)
    ):
    response_text, chatroom_id = await chatbot_system.roleplay_logic.start(req.dict(), profile_id)
    
    if chatroom_id:
        initial_system_input = f"역할놀이 시작: 사용자({req.user_role}), 봇({req.bot_role})"
        background_tasks.add_task(
            chatbot_system.db_manager.save_conversation_to_db, 
            req.session_id, 
            initial_system_input, 
            response_text, 
            chatroom_id, 
            profile_id
        )
    
    return {
        "message": "새로운 역할놀이가 생성되었습니다.",
        "chatroom_id": chatroom_id,
        "response": response_text
    }

@router.post("/{chatroom_id}/talk", summary="역할놀이 대화")
async def handle_roleplay(
    req: ChatRequest, 
    chatroom_id: int, 
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user_id)
    ):
    result = await chatbot_system.roleplay_logic.talk(req.dict(), req.profile_id, chatroom_id)
    
    response_text = result.get("response")
    user_role = result.get("user_role")
    bot_role = result.get("bot_role")

    if result.get("type") == "continue":
        background_tasks.add_task(
            chatbot_system.db_manager.save_conversation_to_db, 
            req.session_id, 
            req.user_input, 
            response_text, 
            chatroom_id, 
            req.profile_id
        )
    
    return {
        "status" : result.get("type"),
        "user_role": user_role,
        "bot_role": bot_role,
        "chatroom_id": chatroom_id,
        "response": response_text
    }