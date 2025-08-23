from fastapi import APIRouter, Depends, HTTPException
from app.services.chatbot_system import chatbot_system
from app.core.security import get_current_user_id

router = APIRouter()

@router.get("/check-today/{profile_id}", summary="오늘 생성된 채팅방 존재 여부 확인")
async def check_chatroom_creation_today(
    profile_id: int,
    user_id: int = Depends(get_current_user_id)
):
    """
    특정 프로필에 대해 오늘 날짜로 생성된 채팅방이 있는지 확인합니다.
    """
    
    was_created = chatbot_system.db_manager.check_chatroom_created_today(profile_id)
    
    return {"created_today": was_created}