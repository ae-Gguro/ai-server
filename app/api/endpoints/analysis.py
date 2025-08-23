# app/api/endpoints/analysis.py 파일의 내용을 아래 코드로 전체 교체하세요.

from fastapi import APIRouter, HTTPException, Depends
from app.services.chatbot_system import chatbot_system
from collections import defaultdict
from app.core.security import get_current_user_id
from datetime import date

router = APIRouter()


@router.get("/summary/daily/{profile_id}", summary="오늘 하루 긍정/부정 단어 요약")
async def get_daily_sentiment_summary(
    profile_id: int,
    user_id: int = Depends(get_current_user_id)
):

    records = chatbot_system.db_manager.get_today_analyses_by_profile_id(profile_id)

    positive_keywords = []
    negative_keywords = []

    for record in records:
        if record['keyword']:
            if record['is_positive']:
                positive_keywords.append(record['keyword'])
            else:
                negative_keywords.append(record['keyword'])
    
    total_count = len(positive_keywords) + len(negative_keywords)
    positive_percentage = 0
    negative_percentage = 0

    if total_count > 0:
        positive_percentage = round((len(positive_keywords) / total_count) * 100)
        negative_percentage = round((len(negative_keywords) / total_count) * 100)
    # ------------------------------------
    
    return {
        "profile_id": profile_id,
        "date": date.today().strftime('%Y-%m-%d'),
        "positive_percentage": positive_percentage, # 긍정 비율 추가
        "negative_percentage": negative_percentage, # 부정 비율 추가
        "positive_keywords": positive_keywords,
        "negative_keywords": negative_keywords
    }


@router.get("/sentiment-summary/{profile_id}", summary="날짜별 긍정/부정 감정 분석 목록 조회")
async def get_sentiment_summary(
    profile_id: int,
    user_id: int = Depends(get_current_user_id)
):
    analyses = chatbot_system.db_manager.get_analyses_by_profile_id(profile_id)
    
    if not analyses:
        raise HTTPException(
            status_code=404,
            detail="분석된 감정 대화 기록이 없습니다."
        )
    
    grouped_analyses = defaultdict(list)

    for record in analyses:
        date_key = record['created_at'].strftime('%Y-%m-%d')
        
        # --- 여기가 수정된 부분입니다 ---
        # keyword 필드를 추가하고, 키 이름을 최종 형식에 맞춥니다.
        formatted_record = {
            "talk_id": record['talk_id'],
            "text": record['summary'],
            "keyword": record['keyword'],
            "positive": record['is_positive']
        }
        
        grouped_analyses[date_key].append(formatted_record)

    return grouped_analyses