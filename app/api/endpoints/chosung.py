# app/api/endpoints/chosung.py 파일의 내용을 아래 코드로 전체 교체하세요.

from fastapi import APIRouter, BackgroundTasks, Depends
from app.models.schemas import ChosungRequest
from app.services.chatbot_system import chatbot_system
from app.core.security import get_current_user_id

router = APIRouter()

@router.post("/talk", summary="초성 퀴즈 시작 및 답변")
async def handle_chosung_quiz(
    req: ChosungRequest,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user_id) 
):
    result_dict = await chatbot_system.chosung_logic.talk(req.dict(), req.profile_id)
    
    response_text_for_db = result_dict.get("message", "")

    chatroom_id = result_dict.get("chatroom_id")
    if chatroom_id:
        background_tasks.add_task(
            chatbot_system.db_manager.save_conversation_to_db, 
            req.session_id, 
            req.user_input, 
            response_text_for_db, 
            chatroom_id, 
            req.profile_id 
        )
    
    return result_dict