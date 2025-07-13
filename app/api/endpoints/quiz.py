from fastapi import APIRouter, BackgroundTasks
from app.models.schemas import QuizRequest 
from app.services.chatbot_system import chatbot_system

router = APIRouter()

@router.post("/talk", summary="퀴즈 시작 및 답변")
async def handle_quiz(req: QuizRequest, background_tasks: BackgroundTasks):
    response_text, chatroom_id = await chatbot_system.quiz_logic.talk(req.dict(), req.profile_id)
    if chatroom_id:
        # 퀴즈 시작 요청시 user_input은 "퀴즈 시작" 같은 더미 텍스트일 수 있음
        background_tasks.add_task(chatbot_system.db_manager.save_conversation_to_db, req.session_id, req.user_input, response_text, chatroom_id, req.profile_id)
    return {"response": response_text}