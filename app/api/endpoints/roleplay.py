# app/api/endpoints/roleplay.py 파일의 내용을 아래 코드로 전체 교체하세요.

from fastapi import APIRouter, BackgroundTasks
from app.models.schemas import RolePlayStartRequest, ChatRequest
from app.services.chatbot_system import chatbot_system

router = APIRouter()

@router.post("/start", summary="역할놀이 시작")
async def start_roleplay(req: RolePlayStartRequest, background_tasks: BackgroundTasks):
    # 역할놀이 시작 로직을 호출하고, 챗봇의 첫 응답과 생성된 chatroom_id를 받습니다.
    response_text, chatroom_id = await chatbot_system.roleplay_logic.start(req.dict(), req.profile_id)
    
    if chatroom_id:
        # DB에 대화 저장 시, 시스템이 기록할 초기 메시지를 생성합니다.
        initial_system_input = f"역할놀이 시작: 사용자({req.user_role}), 봇({req.bot_role})"
        background_tasks.add_task(
            chatbot_system.db_manager.save_conversation_to_db, 
            req.session_id, 
            initial_system_input, 
            response_text, 
            chatroom_id, 
            req.profile_id
        )

    return {
        "message": "새로운 역할놀이가 생성되었습니다.",
        "chatroom_id": chatroom_id,
        "response": response_text
    }

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