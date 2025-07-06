from fastapi import APIRouter, HTTPException
from app.services.chatbot_system import chatbot_system

router = APIRouter()

@router.get("/chatrooms/{profile_id}", summary="프로필별 채팅방 목록 조회")
async def get_chatrooms_by_profile(profile_id: int):
    """
    특정 profile_id에 해당하는 모든 채팅방의 목록을 최신순으로 조회합니다.
    """
    chatrooms = chatbot_system.db_manager.get_chatrooms_by_profile_id(profile_id)
    if not chatrooms:
        raise HTTPException(status_code=404, detail="해당 프로필의 채팅방을 찾을 수 없습니다.")
    return chatrooms

@router.get("/talks/{chatroom_id}", summary="채팅방별 대화 내용 조회")
async def get_talks_by_chatroom(chatroom_id: int):
    """
    특정 chatroom_id에 해당하는 채팅방의 모든 대화 내용을 시간순으로 조회합니다.
    """
    talks = chatbot_system.db_manager.get_talks_by_chatroom_id(chatroom_id)
    if not talks:
        raise HTTPException(status_code=404, detail="해당 채팅방의 대화 내용을 찾을 수 없습니다.")
    return talks

@router.get("/negative-talks/{profile_id}", summary="부정 감정 대화 모아보기")
async def get_negative_talks(profile_id: int):
    """
    특정 profile_id에 대해 사용자가 부정적인 감정을 표현한('positive'=false)
    모든 대화 내용을 최신순으로 조회합니다.
    """
    talks = chatbot_system.db_manager.get_negative_talks_by_profile_id(profile_id)
    if not talks:
        raise HTTPException(
            status_code=404,
            detail="해당 프로필의 부정 감정 대화 기록을 찾을 수 없습니다."
        )
    return talks