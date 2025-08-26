from fastapi import APIRouter, BackgroundTasks, Depends
from app.models.schemas import ChatRequest
from app.services.chatbot_system import chatbot_system
from app.core.security import get_current_user_id

router = APIRouter()

@router.post("/talk", summary="일상 대화")
async def handle_conversation(
    req: ChatRequest, 
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user_id) 
):
    result = await chatbot_system.conversation_logic.talk(req.dict(), user_id, req.profile_id)
    
    chatroom_id = result.get("chatroom_id")
    response_text = result.get("response")

    if result.get("type") == "continue" and chatroom_id:
        background_tasks.add_task(
            chatbot_system.db_manager.save_conversation_to_db, 
            req.session_id, 
            req.user_input, 
            response_text, 
            chatroom_id, 
            req.profile_id
        )
    
    return {
        "chatroom_id": chatroom_id,
        "response": response_text
    }