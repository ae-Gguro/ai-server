import psycopg2
import re
from psycopg2 import Error
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.chat_history import InMemoryChatMessageHistory
from app.core.config import DB_CONFIG
from app.prompts.prompts import ANALYSIS_PROMPT_TEMPLATE, SUMMARIZATION_PROMPT_TEMPLATE

class DatabaseManager:
    def __init__(self, model):
        self.model = model
        self.store = {}
        self.analysis_chain = self._create_analysis_chain()
        self.summarization_chain = self._create_summarization_chain()
        self._ensure_table_exists()

    def _create_db_connection(self):
        try:
            return psycopg2.connect(**DB_CONFIG)
        except Error as e:
            print(f"[DB 오류] PostgreSQL 연결 실패: {e}"); return None

    def _get_session_history(self, session_id: str):
        if session_id not in self.store:
            self.store[session_id] = {'history': InMemoryChatMessageHistory(), 'chatroom_id': None, 'type': 'conversation', 'roleplay_state': None, 'quiz_state': None}
        return self.store[session_id]['history']
    
    def _create_analysis_chain(self):
        try:
            prompt = ChatPromptTemplate.from_template(ANALYSIS_PROMPT_TEMPLATE)
            return prompt | self.model | StrOutputParser()
        except Exception as e:
            print(f"[오류] 감정 분석 체인 생성 실패: {e}"); return None

    def _create_summarization_chain(self):
        try:
            prompt = ChatPromptTemplate.from_template(SUMMARIZATION_PROMPT_TEMPLATE)
            return prompt | self.model | StrOutputParser()
        except Exception as e:
            print(f"[오류] 요약 체인 생성 실패: {e}"); return None

    def _ensure_table_exists(self):
        conn = self._create_db_connection()
        if conn is None: return
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chatroom (
                        id BIGSERIAL PRIMARY KEY, profile_id BIGINT NOT NULL, topic TEXT, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );""")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS talk (
                        id BIGSERIAL PRIMARY KEY, chatroom_id BIGINT NOT NULL REFERENCES chatroom(id), category VARCHAR(50) NOT NULL,
                        content TEXT NOT NULL, session_id VARCHAR(255), role VARCHAR(255), created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP, profile_id BIGINT NOT NULL, "like" BOOLEAN,
                        positive BOOLEAN DEFAULT TRUE, keywords TEXT[]
                    );""")
                cursor.execute("""
                    CREATE OR REPLACE FUNCTION update_updated_at_column() RETURNS TRIGGER AS $$
                    BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
                    $$ language 'plpgsql';""")
                cursor.execute("""
                    DROP TRIGGER IF EXISTS update_talk_updated_at ON talk;
                    CREATE TRIGGER update_talk_updated_at BEFORE UPDATE ON talk FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();""")
            conn.commit()
            print("[DB 정보] 'chatroom' 및 'talk' 테이블 준비 완료.")
        except Error as e:
            print(f"[DB 오류] 테이블 생성 실패: {e}"); conn.rollback()
        finally:
            if conn: conn.close()

    async def summarize_and_close_room(self, session_id: str):
        session_state = self.store.get(session_id)
        if not session_state or not session_state.get('chatroom_id'):
            print(f"세션({session_id})에 종료할 채팅방이 없습니다.")
            return

        current_chatroom_id = session_state['chatroom_id']
        history = session_state['history']
        
        summary = ""
        room_type = session_state.get('type', 'conversation')
        quiz_info = session_state.get('quiz_state')

        if room_type == 'quiz' and quiz_info:
            summary = f"[퀴즈] {quiz_info['quiz_item']['question']}"
        elif history.messages:
            full_history_str = "\n".join([f"{msg.type}: {msg.content}" for msg in history.messages])
            summary_text = await self.summarization_chain.ainvoke({"history": full_history_str})
            if room_type == 'roleplay' and session_state.get('roleplay_state'):
                summary = f"[역할놀이] {summary_text.strip()}"
            else:
                summary = f"[일상대화] {summary_text.strip()}"

        if summary:
            conn = self._create_db_connection()
            if conn is None: return
            try:
                with conn.cursor() as cursor:
                    cursor.execute("UPDATE chatroom SET topic = %s WHERE id = %s", (summary, current_chatroom_id))
                    conn.commit()
                print(f"채팅방({current_chatroom_id}) 요약 완료: {summary}")
            except Error as e:
                print(f"[DB 오류] 채팅방 요약 실패: {e}"); conn.rollback()
            finally:
                if conn: conn.close()

        self.store[session_id] = {'history': InMemoryChatMessageHistory(), 'chatroom_id': None, 'type': 'conversation', 'roleplay_state': None, 'quiz_state': None}
        print(f"세션({session_id})이 완전히 종료 및 초기화되었습니다.")

    async def create_new_chatroom(self, session_id: str, profile_id: int, room_type: str):
        await self.summarize_and_close_room(session_id)
        session_state = self.store.setdefault(session_id, {})
        session_state['history'] = InMemoryChatMessageHistory()
        session_state['type'] = room_type

        conn = self._create_db_connection()
        if conn is None: return None
        try:
            with conn.cursor() as cursor:
                topic_map = {'quiz': "새로운 퀴즈", 'roleplay': "새로운 역할놀이", 'conversation': "새로운 대화"}
                topic = topic_map.get(room_type, "새로운 대화")
                cursor.execute("INSERT INTO chatroom (profile_id, topic) VALUES (%s, %s) RETURNING id", (profile_id, topic))
                new_chatroom_id = cursor.fetchone()[0]
                session_state['chatroom_id'] = new_chatroom_id
                conn.commit()
                print(f"새 채팅방 생성 (타입: {room_type}, ID: {new_chatroom_id})")
                return new_chatroom_id
        except Error as e:
            print(f"[DB 오류] 새 채팅방 생성 실패: {e}"); conn.rollback(); return None
        finally:
            if conn: conn.close()

    async def save_conversation_to_db(self, session_id: str, user_input: str, bot_response: str, chatroom_id: int, profile_id: int):
        session_state = self.store.get(session_id, {})
        if not self.analysis_chain:
            is_positive, keywords_list = True, []
        else:
            try:
                analysis_result = await self.analysis_chain.ainvoke({"text": user_input})
                is_positive = "부정" not in analysis_result
                keywords_match = re.search(r"\[키워드:\s*(.*)\]", analysis_result)
                keywords_list = [k.strip() for k in keywords_match.group(1).split(',') if k.strip()] if keywords_match else []
            except Exception as e:
                print(f"[오류] 분석 중 오류 발생: {e}"); is_positive, keywords_list = True, []

        conn = self._create_db_connection()
        if conn is None: return
        try:
            with conn.cursor() as cursor:
                query = """
                    INSERT INTO talk (session_id, role, content, category, profile_id, positive, keywords, "like", chatroom_id) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, %s)
                """
                category_map = {'quiz': 'SAFETYSTUDY', 'roleplay': 'ROLEPLAY', 'conversation': 'LIFESTYLEHABIT'}
                category = category_map.get(session_state.get('type', 'conversation'), 'LIFESTYLEHABIT')
                
                cursor.execute(query, (session_id, 'user', user_input, category, profile_id, is_positive, keywords_list, chatroom_id))
                cursor.execute(query, (session_id, 'bot', bot_response, category, profile_id, True, [], chatroom_id))
            conn.commit()
            print(f"✅ 채팅방[{chatroom_id}] 대화 저장 완료")
        except Error as e:
            print(f"[DB 오류] 메시지 저장 실패: {e}"); conn.rollback()
        finally:
            if conn: conn.close()