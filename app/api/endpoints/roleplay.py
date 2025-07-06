from fastapi import APIRouter, BackgroundTasks
# 수정된 모델을 import 합니다.
from app.models.schemas import RolePlayStartRequest, ChatRequest
from app.services.chatbot_system import chatbot_system

router = APIRouter()

@router.post("/start", summary="역할놀이 시작")
async def start_roleplay(req: RolePlayStartRequest, background_tasks: BackgroundTasks):
    initial_system_input = f"역할놀이 시작: 사용자({req.user_role}), 봇({req.bot_role})"
    
    response_text, chatroom_id = await chatbot_system.roleplay_logic.start(req.dict(), req.profile_id)
    if chatroom_id:
        background_tasks.add_task(
            chatbot_system.db_manager.save_conversation_to_db, 
            req.session_id, 
            initial_system_input, 
            response_text, 
            chatroom_id, 
            req.profile_id
        )
    return {"response": response_text}

@router.post("/talk", summary="역할놀이 대화")
async def handle_roleplay(req: ChatRequest, background_tasks: BackgroundTasks):
    response_text, chatroom_id = await chatbot_system.roleplay_logic.talk(req.dict(), req.profile_id)
    if chatroom_id:
        background_tasks.add_task(
            chatbot_system.db_manager.save_conversation_to_db, 
            req.session_id, 
            req.user_input, 
            response_text, 
            chatroom_id, 
            req.profile_id
        )
    return {"response": response_text}