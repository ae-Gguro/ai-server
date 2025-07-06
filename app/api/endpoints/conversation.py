from fastapi import APIRouter, BackgroundTasks
from app.models.schemas import ChatRequest
from app.services.chatbot_system import chatbot_system

router = APIRouter()

@router.post("/talk", summary="일상 대화")
async def handle_conversation(req: ChatRequest, background_tasks: BackgroundTasks):
    response_text, chatroom_id = await chatbot_system.conversation_logic.talk(req.dict(), req.profile_id)
    if chatroom_id:
        background_tasks.add_task(chatbot_system.db_manager.save_conversation_to_db, req.session_id, req.user_input, response_text, chatroom_id, req.profile_id)
    return {"response": response_text}