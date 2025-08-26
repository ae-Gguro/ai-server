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

    def get_weekly_report_from_db(self, profile_id: int, start_date: date):
        conn = self.db_manager._create_db_connection()
        if conn is None: return None
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT report_content FROM weekly_reports WHERE profile_id = %s AND start_date = %s",
                    (profile_id, start_date)
                )
                report = cursor.fetchone()
                return report[0] if report else None
        except Exception as e:
            print(f"[DB 오류] 주간 리포트 조회 실패: {e}")
            return None
        finally:
            if conn: conn.close()

    def save_weekly_report_to_db(self, profile_id: int, start_date: date, end_date: date, report_content: str):
        conn = self.db_manager._create_db_connection()
        if conn is None: return
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO weekly_reports (profile_id, start_date, end_date, report_content) VALUES (%s, %s, %s, %s)",
                    (profile_id, start_date, end_date, report_content)
                )
            conn.commit()
            print(f"✅ 주간 리포트 저장 완료 (profile_id: {profile_id}, start_date: {start_date})")
        except Exception as e:
            print(f"[DB 오류] 주간 리포트 저장 실패: {e}"); conn.rollback()
        finally:
            if conn: conn.close()

    async def generate_and_get_weekly_report(self, profile_id: int):
        today = date.today()
        start_of_last_week = today - timedelta(days=today.weekday() + 7)
        
        existing_report = self.get_weekly_report_from_db(profile_id, start_of_last_week)
        if existing_report:
            print(f"✅ 기존 주간 리포트 조회 성공 (profile_id: {profile_id})")
            return {"profile_id": profile_id, "advice": existing_report}

        print(f"⏳ 기존 리포트 없음. LLM으로 새로 생성 시작 (profile_id: {profile_id})")
        start_of_this_week = start_of_last_week + timedelta(days=7)
        records = self.db_manager.get_analyses_by_date_range(profile_id, start_of_last_week, start_of_this_week)
        if not records:
            raise HTTPException(status_code=404, detail="지난주에 분석된 대화 기록이 없습니다.")

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
        
        pos_kw_str = ", ".join([f"'{kw}'({count}회)" for kw, count in positive_keywords.most_common(5)])
        neg_kw_str = ", ".join([f"'{kw}'({count}회)" for kw, count in negative_keywords.most_common(5)])
        daily_summary_str = (f"오전(긍정 {time_summary['오전']['긍정']}회, 부정 {time_summary['오전']['부정']}회), "
                             f"오후(긍정 {time_summary['오후']['긍정']}회, 부정 {time_summary['오후']['부정']}회), "
                             f"저녁(긍정 {time_summary['저녁']['긍정']}회, 부정 {time_summary['저녁']['부정']}회)")
        
        prompt = ChatPromptTemplate.from_template(RELATIONSHIP_ADVICE_PROMPT_TEMPLATE)
        chain = prompt | self.model | StrOutputParser()
        
        advice_markdown = await chain.ainvoke({
            "positive_keywords": pos_kw_str or "없음",
            "negative_keywords": neg_kw_str or "없음",
            "daily_summary": daily_summary_str
        })
        
        self.save_weekly_report_to_db(profile_id, start_of_last_week, start_of_this_week - timedelta(days=1), advice_markdown)
        return {"profile_id": profile_id, "advice": advice_markdown}