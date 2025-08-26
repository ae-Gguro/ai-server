from fastapi import APIRouter, HTTPException, Depends, Query
from app.services.chatbot_system import chatbot_system
from collections import defaultdict
from app.core.security import get_current_user_id
from collections import defaultdict, Counter
from datetime import date, timedelta
import calendar

router = APIRouter()


@router.get("/summary/daily/{profile_id}", summary="특정 날짜 긍정/부정 단어 요약")
async def get_daily_sentiment_summary(
    profile_id: int,
    # 쿼리 파라미터로 'date'를 받습니다. (예: ?date=2025-08-26)
    target_date: date = Query(..., description="조회할 날짜 (YYYY-MM-DD)"),
    user_id: int = Depends(get_current_user_id)
):
    
    # 1. DB에서 해당 날짜의 분석 기록만 가져옴
    records = chatbot_system.db_manager.get_analyses_by_date(profile_id, target_date)

    positive_keywords = []
    negative_keywords = []

    # 2. 긍정/부정 키워드 분리
    for record in records:
        if record['keyword']:
            if record['is_positive']:
                positive_keywords.append(record['keyword'])
            else:
                negative_keywords.append(record['keyword'])
    
    # 3. 최종 응답 형식 구성
    total_count = len(positive_keywords) + len(negative_keywords)
    positive_percentage = round((len(positive_keywords) / total_count) * 100) if total_count > 0 else 0
    negative_percentage = round((len(negative_keywords) / total_count) * 100) if total_count > 0 else 0
    
    return {
        "profile_id": profile_id,
        "date": target_date.strftime('%Y-%m-%d'),
        "positive_percentage": positive_percentage,
        "negative_percentage": negative_percentage,
        "positive_keywords": positive_keywords,
        "negative_keywords": negative_keywords
    }


@router.get("/summary/weekly/{profile_id}", summary="지난주 긍정/부정 종합 리포트")
async def get_weekly_sentiment_summary(
    profile_id: int,
    user_id: int = Depends(get_current_user_id)
):
    today = date.today()
    last_monday = today - timedelta(days=today.weekday() + 7)
    this_monday = today - timedelta(days=today.weekday())

    records = chatbot_system.db_manager.get_analyses_by_date_range(profile_id, last_monday, this_monday)

    if not records:
        raise HTTPException(status_code=404, detail="지난주에 분석된 대화 기록이 없습니다.")

    positive_keyword_counts = Counter()
    negative_keyword_counts = Counter()
    daily_summary_data = {i: {'positive': 0, 'negative': 0} for i in range(7)}

    for record in records:
        day_index = record['created_at'].weekday()
        if record['keyword']:
            if record['is_positive']:
                positive_keyword_counts[record['keyword']] += 1
                daily_summary_data[day_index]['positive'] += 1
            else:
                negative_keyword_counts[record['keyword']] += 1
                daily_summary_data[day_index]['negative'] += 1
    
    day_names = ["월", "화", "수", "목", "금", "토", "일"]
    daily_ratios = []
    for i in range(7):
        # 지난 주 각 요일의 실제 날짜를 계산
        current_date = last_monday + timedelta(days=i)
        day_stat = daily_summary_data[i]
        total = day_stat['positive'] + day_stat['negative']
        ratio = {
            "date": current_date.strftime('%Y-%m-%d'), #
            "day": day_names[i],
            "positive_percentage": round((day_stat['positive'] / total) * 100) if total > 0 else 0,
            "negative_percentage": round((day_stat['negative'] / total) * 100) if total > 0 else 0
        }
        daily_ratios.append(ratio)
        
    return {
        "profile_id": profile_id,
        "start_date": last_monday.strftime('%Y-%m-%d'),
        "end_date": (this_monday - timedelta(days=1)).strftime('%Y-%m-%d'),
        "top_positive_keywords": [{"keyword": kw, "count": count} for kw, count in positive_keyword_counts.most_common(5)],
        "top_negative_keywords": [{"keyword": kw, "count": count} for kw, count in negative_keyword_counts.most_common(5)],
        "daily_summary": daily_ratios
    }


@router.get("/sentiment-summary/{profile_id}", summary="전체 기간 날짜별 분석 목록 조회")
async def get_all_sentiment_summary(
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
        
        formatted_record = {
            "talk_id": record['talk_id'],
            "chatroom_id": record['chatroom_id'],
            "text": record['summary'],      
            "keyword": record['keyword'],
            "positive": record['is_positive'] 
        }
        grouped_analyses[date_key].append(formatted_record)
        
    return grouped_analyses


@router.get("/summary/monthly/{profile_id}", summary="월간 긍정/부정 상태 리포트")
async def get_monthly_sentiment_summary(
    profile_id: int,
    year: int = Query(..., description="조회할 년도 (예: 2025)"),
    month: int = Query(..., ge=1, le=12, description="조회할 월 (1~12)"),
    user_id: int = Depends(get_current_user_id)
):
    # 1. DB에서 해당 월의 데이터 조회
    records = chatbot_system.db_manager.get_analyses_by_month(profile_id, year, month)
    
    # 2. 일자별 긍정/부정 카운트 집계
    daily_counts = defaultdict(lambda: {'positive': 0, 'negative': 0})
    for record in records:
        day = record['created_at'].day
        if record['is_positive']:
            daily_counts[day]['positive'] += 1
        else:
            daily_counts[day]['negative'] += 1
            
    # 3. 해당 월의 마지막 날짜 계산
    _, num_days_in_month = calendar.monthrange(year, month)
    
    daily_status_list = []
    total_positive = 0
    total_negative = 0

    # 4. 1일부터 마지막 날까지 순회하며 상태 결정
    for day in range(1, num_days_in_month + 1):
        counts = daily_counts[day]
        pos_count = counts['positive']
        neg_count = counts['negative']
        
        total_positive += pos_count
        total_negative += neg_count
        
        status = "none"
        if pos_count > neg_count:
            status = "positive"
        elif neg_count > pos_count:
            status = "negative"
        elif pos_count != 0 and pos_count == neg_count:
            status = "neutral"
            
        daily_status_list.append({"day": day, "status": status})
        
    # 5. 월간 전체 긍정 비율 계산
    total_interactions = total_positive + total_negative
    monthly_positive_percentage = round((total_positive / total_interactions) * 100) if total_interactions > 0 else 0

    return {
        "profile_id": profile_id,
        "year": year,
        "month": month,
        "monthly_positive_percentage": monthly_positive_percentage,
        "daily_statuses": daily_status_list
    }