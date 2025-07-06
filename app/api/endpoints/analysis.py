from fastapi import APIRouter, HTTPException
from app.services.chatbot_system import chatbot_system

router = APIRouter()

@router.get("/sentiment-summary/{profile_id}", summary="부정 감정 대화 분석 목록 조회")
async def get_sentiment_summary(profile_id: int):
    """
    미리 분석하여 저장해 둔, 아이의 부정 감정 대화 분석 결과
    목록을 최신순으로 조회합니다. (빠른 응답)
    """
    analyses = chatbot_system.db_manager.get_analyses_by_profile_id(profile_id)
    
    if not analyses:
        raise HTTPException(
            status_code=404,
            detail="분석된 부정 감정 대화 기록이 없습니다."
        )
    return {"analyses": analyses}