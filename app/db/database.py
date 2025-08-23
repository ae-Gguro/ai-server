import psycopg2
import re
from psycopg2 import Error
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.chat_history import InMemoryChatMessageHistory
from app.core.config import DB_CONFIG
from app.prompts.prompts import (
    ANALYSIS_PROMPT_TEMPLATE,
    SUMMARIZATION_PROMPT_TEMPLATE,
    SINGLE_NEGATIVE_TALK_ANALYSIS_PROMPT,
    SINGLE_POSITIVE_TALK_ANALYSIS_PROMPT
)

class DatabaseManager:
    def __init__(self, model):
        self.model = model
        self.store = {}
        self.summarization_chain = self._create_summarization_chain()
        self.sentiment_keyword_chain = self._create_sentiment_keyword_chain()
        self.analysis_chains = {
            True: self._create_single_talk_analysis_chain(SINGLE_POSITIVE_TALK_ANALYSIS_PROMPT),
            False: self._create_single_talk_analysis_chain(SINGLE_NEGATIVE_TALK_ANALYSIS_PROMPT)
        }
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
    
    def _create_sentiment_keyword_chain(self):
        try:
            prompt = ChatPromptTemplate.from_template(ANALYSIS_PROMPT_TEMPLATE)
            return prompt | self.model | StrOutputParser()
        except Exception as e:
            print(f"[오류] 감정/키워드 분석 체인 생성 실패: {e}"); return None

    def _create_summarization_chain(self):
        try:
            prompt = ChatPromptTemplate.from_template(SUMMARIZATION_PROMPT_TEMPLATE)
            return prompt | self.model | StrOutputParser()
        except Exception as e:
            print(f"[오류] 요약 체인 생성 실패: {e}"); return None
            
    def _create_single_talk_analysis_chain(self, prompt_template):
        try:
            prompt = ChatPromptTemplate.from_template(prompt_template)
            return prompt | self.model | StrOutputParser()
        except Exception as e:
            print(f"[오류] 단일 대화 분석 체인 생성 실패: {e}"); return None

    def _ensure_table_exists(self):
        conn = self._create_db_connection()
        if conn is None: return
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chatroom (
                        id BIGSERIAL PRIMARY KEY, 
                        profile_id BIGINT NOT NULL, 
                        topic TEXT, 
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );""")

                cursor.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'sentiment_type') THEN
                            CREATE TYPE sentiment_type AS ENUM ('긍정', '부정', '일반');
                        END IF;
                    END$$;
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS talk (
                        id BIGSERIAL PRIMARY KEY,
                        chatroom_id BIGINT NOT NULL REFERENCES chatroom(id) ON DELETE CASCADE,
                        profile_id BIGINT NOT NULL,
                        category VARCHAR(50) NOT NULL,
                        content TEXT NOT NULL,
                        session_id VARCHAR(255),
                        role VARCHAR(255),
                        created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        "like" BOOLEAN,
                        sentiment sentiment_type DEFAULT '일반',
                        keywords TEXT[]
                    );""")
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS analysis (
                        id BIGSERIAL PRIMARY KEY,
                        talk_id BIGINT NOT NULL UNIQUE REFERENCES talk(id),
                        profile_id BIGINT NOT NULL,
                        summary TEXT NOT NULL,
                        keyword TEXT, -- 키워드 저장을 위한 컬럼 추가
                        is_positive BOOLEAN NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );""")
                
                cursor.execute("""
                    CREATE OR REPLACE FUNCTION update_updated_at_column() RETURNS TRIGGER AS $$
                    BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
                    $$ language 'plpgsql';""")
                
                cursor.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_talk_updated_at') THEN
                            CREATE TRIGGER update_talk_updated_at 
                            BEFORE UPDATE ON talk 
                            FOR EACH ROW 
                            EXECUTE FUNCTION update_updated_at_column();
                        END IF;
                    END$$;
                """)

            conn.commit()
            print("[DB 정보] 테이블 상태 확인 및 준비 완료.")
        except Error as e:
            print(f"[DB 오류] 테이블 생성/확인 실패: {e}"); conn.rollback()
        finally:
            if conn: conn.close()

    async def summarize_and_close_room(self, session_id: str):
        session_state = self.store.get(session_id)
        if not session_state or not session_state.get('chatroom_id'):
            return
        current_chatroom_id = session_state['chatroom_id']
        history = session_state['history']
        summary = ""
        room_type = session_state.get('type', 'conversation')
        quiz_info = session_state.get('quiz_state')
        if room_type == 'quiz' and quiz_info:
            quiz_topic = quiz_info.get('topic', '안전 퀴즈')
            summary = f"[{quiz_topic}] 퀴즈를 완료했어요."
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
            
    async def _analyze_and_save_talk_analysis(self, talk_id: int, profile_id: int, user_input: str, is_positive: bool):
        analysis_chain = self.analysis_chains.get(is_positive)
        if not analysis_chain: return

        try:
            raw_response = await analysis_chain.ainvoke({"user_talk": user_input})
            
            summary_match = re.search(r"\[요약문\]:\s*(.*)", raw_response)
            keyword_match = re.search(r"\[핵심 단어\]:\s*(.*)", raw_response)
            
            clean_summary = summary_match.group(1).strip() if summary_match else "분석 결과를 요약하는 데 실패했어요."
            clean_keyword = keyword_match.group(1).strip() if keyword_match else None
            print(clean_keyword)
            print(clean_summary)
            conn = self._create_db_connection()
            if conn is None: return
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO analysis (talk_id, profile_id, summary, keyword, is_positive) VALUES (%s, %s, %s, %s, %s)",
                        (talk_id, profile_id, clean_summary, clean_keyword, is_positive)
                    )
                conn.commit()
                print(f"✅ 대화 분석 완료 및 저장 (talk_id: {talk_id}, positive: {is_positive})")
            except Error as e:
                print(f"[DB 오류] 분석 결과 저장 실패: {e}"); conn.rollback()
            finally:
                if conn: conn.close()
        except Exception as e:
            print(f"[오류] 대화 분석 중 문제 발생: {e}")
            

    async def save_conversation_to_db(self, session_id: str, user_input: str, bot_response: str, chatroom_id: int, profile_id: int):
        sentiment = "일반"
        keywords_list = []
        if self.sentiment_keyword_chain:
            try:
                analysis_result = await self.sentiment_keyword_chain.ainvoke({"text": user_input})
                
                if "[판단: 긍정]" in analysis_result:
                    sentiment = "긍정"
                elif "[판단: 부정]" in analysis_result:
                    sentiment = "부정"
                
                keywords_match = re.search(r"\[키워드:\s*(.*)\]", analysis_result)
                keywords_list = [k.strip() for k in keywords_match.group(1).split(',') if k.strip()] if keywords_match else []
            except Exception as e:
                print(f"[오류] 분석 중 오류 발생: {e}")

        conn = self._create_db_connection()
        if conn is None: return
        user_talk_id = None
        try:
            with conn.cursor() as cursor:
                category_map = {'quiz': 'SAFETYSTUDY', 'roleplay': 'ROLEPLAY', 'conversation': 'LIFESTYLEHABIT'}
                category = category_map.get(self.store.get(session_id, {}).get('type', 'conversation'), 'LIFESTYLEHABIT')
                
                cursor.execute(
                    """INSERT INTO talk (session_id, role, content, category, profile_id, sentiment, keywords, "like", chatroom_id) 
                       VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, %s) RETURNING id""",
                    (session_id, 'user', user_input, category, profile_id, sentiment, keywords_list, chatroom_id)
                )
                user_talk_id = cursor.fetchone()[0]

                cursor.execute(
                    """INSERT INTO talk (session_id, role, content, category, profile_id, "like", chatroom_id) 
                       VALUES (%s, 'bot', %s, %s, %s, NULL, %s)""",
                    (session_id, bot_response, category, profile_id, chatroom_id)
                )
            conn.commit()
            print(f"✅ 채팅방[{chatroom_id}] 대화 저장 완료")
        except Error as e:
            print(f"[DB 오류] 메시지 저장 실패: {e}"); conn.rollback()
        finally:
            if conn: conn.close()

        if sentiment != "일반" and keywords_list and user_talk_id:
            is_positive_for_analysis = (sentiment == "긍정")
            await self._analyze_and_save_talk_analysis(user_talk_id, profile_id, user_input, is_positive_for_analysis)

    def get_analyses_by_profile_id(self, profile_id: int):
        conn = self._create_db_connection()
        if conn is None: return []
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, talk_id, summary, keyword, is_positive, created_at
                    FROM analysis
                    WHERE profile_id = %s
                    ORDER BY created_at DESC
                """, (profile_id,))
                analyses = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in analyses]
        except Error as e:
            print(f"[DB 오류] 분석 목록 조회 실패: {e}")
            return []
        finally:
            if conn: conn.close()


    def get_chatrooms_by_profile_id(self, profile_id: int):
        conn = self._create_db_connection()
        if conn is None: return []
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, topic, created_at
                    FROM chatroom
                    WHERE profile_id = %s
                    ORDER BY created_at DESC
                """, (profile_id,))
                chatrooms = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in chatrooms]
        except Error as e:
            print(f"[DB 오류] 채팅방 목록 조회 실패: {e}")
            return []
        finally:
            if conn: conn.close()

    def get_talks_by_chatroom_id(self, chatroom_id: int):
        # ... (이하 로직 변경 없음)
        conn = self._create_db_connection()
        if conn is None: return []
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, role, content, created_at
                    FROM talk
                    WHERE chatroom_id = %s
                    ORDER BY created_at ASC
                """, (chatroom_id,))
                talks = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in talks]
        except Error as e:
            print(f"[DB 오류] 대화 내용 조회 실패: {e}")
            return []
        finally:
            if conn: conn.close()

    def update_talk_feedback(self, talk_id: int, like_status: bool):
        # ... (이하 로직 변경 없음)
        conn = self._create_db_connection()
        if conn is None: return False
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """UPDATE talk SET "like" = %s WHERE id = %s""",
                    (like_status, talk_id)
                )
            conn.commit()
            return cursor.rowcount > 0
        except Error as e:
            print(f"[DB 오류] 피드백 업데이트 실패: {e}")
            conn.rollback()
            return False
        finally:
            if conn: conn.close()

    def get_negative_talks_by_profile_id(self, profile_id: int):
        conn = self._create_db_connection()
        if conn is None: return []
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT tk.id, tk.content, tk.created_at, cr.topic
                    FROM talk AS tk
                    JOIN chatroom AS cr ON tk.chatroom_id = cr.id
                    WHERE tk.profile_id = %s AND tk.sentiment = '부정'
                    ORDER BY tk.created_at DESC
                """, (profile_id,))
                talks = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in talks]
        except Error as e:
            print(f"[DB 오류] 부정 감정 대화 조회 실패: {e}")
            return []
        finally:
            if conn: conn.close()