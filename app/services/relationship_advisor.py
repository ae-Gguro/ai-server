import re
from datetime import date, timedelta
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.prompts.prompts import RELATIONSHIP_ADVICE_PROMPT_TEMPLATE
from collections import Counter
from fastapi import HTTPException

class RelationshipAdvisor:
    def __init__(self, model, db_manager):
        self.model = model
        self.db_manager = db_manager

    async def generate_advice(self, user_id: int, profile_id: int):
        # 조회 시점과 상관없이 항상 '지난주 월요일~일요일'을 계산
        today = date.today()
        start_of_last_week = today - timedelta(days=today.weekday() + 7)
        start_of_this_week = start_of_last_week + timedelta(days=7)

        # DB에서 해당 기간의 분석 기록 조회
        records = self.db_manager.get_analyses_by_date_range(profile_id, start_of_last_week, start_of_this_week)
        
        if not records:
            # 데이터가 없을 경우 바로 HTTPException을 발생시켜 종료
            raise HTTPException(status_code=404, detail="지난주에 분석된 대화 기록이 없습니다.")

        # 데이터 가공: 키워드 빈도수 및 시간대별 반응 집계
        positive_keywords = Counter()
        negative_keywords = Counter()
        time_summary = {"오전": {"긍정": 0, "부정": 0}, "오후": {"긍정": 0, "부정": 0}, "저녁": {"긍정": 0, "부정": 0}}

        for record in records:
            hour = record['created_at'].hour
            if record['keyword']:
                if record['is_positive']:
                    positive_keywords[record['keyword']] += 1
                else:
                    negative_keywords[record['keyword']] += 1
            
            if 6 <= hour < 12: time_period = "오전"
            elif 12 <= hour < 18: time_period = "오후"
            else: time_period = "저녁"

            if record['is_positive']:
                time_summary[time_period]["긍정"] += 1
            else:
                time_summary[time_period]["부정"] += 1
        
        # 프롬프트에 주입할 데이터 문자열로 변환
        pos_kw_str = ", ".join([f"'{kw}'({count}회)" for kw, count in positive_keywords.most_common(5)])
        neg_kw_str = ", ".join([f"'{kw}'({count}회)" for kw, count in negative_keywords.most_common(5)])
        daily_summary_str = (f"오전(긍정 {time_summary['오전']['긍정']}회, 부정 {time_summary['오전']['부정']}회), "
                             f"오후(긍정 {time_summary['오후']['긍정']}회, 부정 {time_summary['오후']['부정']}회), "
                             f"저녁(긍정 {time_summary['저녁']['긍정']}회, 부정 {time_summary['저녁']['부정']}회)")
        
        # LLM 체인 구성 및 호출
        prompt = ChatPromptTemplate.from_template(RELATIONSHIP_ADVICE_PROMPT_TEMPLATE)
        chain = prompt | self.model | StrOutputParser()
        
        advice_markdown = await chain.ainvoke({
            "positive_keywords": pos_kw_str or "없음",
            "negative_keywords": neg_kw_str or "없음",
            "daily_summary": daily_summary_str
        })
        
        # 최종 응답 반환
        return {
            "profile_id": profile_id,
            "advice": advice_markdown
        }