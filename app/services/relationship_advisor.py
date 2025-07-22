import psycopg2
from psycopg2 import Error
from datetime import date
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.core.config import DB_CONFIG
from app.prompts.prompts import RELATIONSHIP_ADVICE_PROMPT_TEMPLATE

class RelationshipAdvisor:
    def __init__(self, model):
        self.model = model

    def _fetch_today_conversations(self, profile_id: int):
        conn = None
        cursor = None
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()
            today = date.today()
            cursor.execute("""
                SELECT role, content 
                FROM talk 
                WHERE profile_id = %s AND DATE(created_at) = %s
                AND category = 'LIFESTYLEHABIT'
                ORDER BY created_at ASC
            """, (profile_id, today))
            return cursor.fetchall()
        except Error as e:
            print(f"[DB 오류] 대화 내용 조회 실패: {e}")
            return []
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    async def generate_advice(self, profile_id: int):
        conversations = self._fetch_today_conversations(profile_id)
        
        if not conversations:
            return {"profile_id": profile_id, "advice": "오늘의 대화 내용이 없어 조언을 생성할 수 없습니다."}

        child_talks = [f"- {content}" for role, content in conversations if role == 'user']
        if not child_talks:
            return {"profile_id": profile_id, "advice": "오늘 아이의 대화 내용이 없어 조언을 생성할 수 없습니다."}
            
        conversation_log = "\n".join(child_talks)

        prompt = ChatPromptTemplate.from_template(RELATIONSHIP_ADVICE_PROMPT_TEMPLATE)
        
        chain = prompt | self.model | StrOutputParser()
        result = await chain.ainvoke({"conversation_log": conversation_log})
        
        return {"profile_id": profile_id, "advice": result}