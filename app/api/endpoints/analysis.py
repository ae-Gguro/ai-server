# app/api/endpoints/analysis.py 파일의 내용을 아래 코드로 전체 교체하세요.

from fastapi import APIRouter, HTTPException
from app.services.chatbot_system import chatbot_system
from collections import defaultdict # 그룹화를 위해 defaultdict를 사용합니다.

router = APIRouter()

@router.get("/sentiment-summary/{profile_id}", summary="날짜별 긍정/부정 감정 분석 목록 조회")
async def get_sentiment_summary(profile_id: int):
    """
    프로필에 대해 저장된 모든 긍정/부정 감정 분석 결과를
    날짜별로 그룹화하여 반환합니다.
    """
    analyses = chatbot_system.db_manager.get_analyses_by_profile_id(profile_id)
    
    if not analyses:
        raise HTTPException(
            status_code=404,
            detail="분석된 감정 대화 기록이 없습니다."
        )
    
    grouped_analyses = defaultdict(list)

    for record in analyses:
        date_key = record['created_at'].strftime('%Y-%m-%d')
        
        formatted_record = {
            "talk_id": record['talk_id'],
            "text": record['summary'],     
            "positive": record['is_positive'] 
        }
        
        grouped_analyses[date_key].append(formatted_record)

    return grouped_analyses