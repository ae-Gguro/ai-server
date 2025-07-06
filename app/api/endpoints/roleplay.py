from fastapi import APIRouter, BackgroundTasks
from app.models.schemas import RolePlayRequest, ChatRequest
from app.services.chatbot_system import chatbot_system

router = APIRouter()

@router.post("/start", summary="역할놀이 시작")
async def start_roleplay(req: RolePlayRequest, background_tasks: BackgroundTasks):

    initial_user_input = req.user_input if req.user_input else f"{req.user_role} 역할 시작"
    
    response_text, chatroom_id = await chatbot_system.roleplay_logic.start(req.dict(), req.profile_id)
    if chatroom_id:
        # Save the initial message exchange
        background_tasks.add_task(chatbot_system.db_manager.save_conversation_to_db, req.session_id, initial_user_input, response_text, chatroom_id, req.profile_id)
    return {"response": response_text}

@router.post("/talk", summary="역할놀이 대화")
async def handle_roleplay(req: ChatRequest, background_tasks: BackgroundTasks):
    response_text, chatroom_id = await chatbot_system.roleplay_logic.talk(req.dict(), req.profile_id)
    if chatroom_id:
        background_tasks.add_task(chatbot_system.db_manager.save_conversation_to_db, req.session_id, req.user_input, response_text, chatroom_id, req.profile_id)
    return {"response": response_text}