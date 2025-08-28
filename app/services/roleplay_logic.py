from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.output_parsers import StrOutputParser
from app.db.database import DatabaseManager
from app.prompts.prompts import ROLE_PROMPTS

# 대화 중단을 감지하기 위한 키워드 리스트
STOP_KEYWORDS = ["그만", "끝", "종료", "이제 그만", "그만하고 싶어"]

class RolePlayLogic:
    def __init__(self, model, db_manager: DatabaseManager):
        self.model = model
        self.db_manager = db_manager
        self.conversational_chain = self._create_conversational_chain()
    
    def _create_conversational_chain(self):
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", "{system_prompt}"),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
            ])
            chain = prompt | self.model | StrOutputParser()
            return RunnableWithMessageHistory(
                chain,
                self.db_manager._get_session_history,
                input_messages_key="input",
                history_messages_key="chat_history",
                system_message_key="system_prompt"
            )
        except Exception as e:
            print(f"[오류] 역할놀이 체인 생성 실패: {e}"); return None
        
    async def start(self, req: dict, profile_id: int):
        session_id = req['session_id']
        user_role = req['user_role']
        bot_role = req['bot_role']

        chatroom_id = await self.db_manager.create_new_chatroom(session_id, profile_id, 'roleplay')
        
        session_state = self.db_manager.store.setdefault(session_id, {})
        session_state['roleplay_state'] = {"user_role": user_role, "bot_role": bot_role}
        
        print(f"🎭 세션 [{session_id}] 역할놀이 시작: 사용자='{user_role}', 챗봇='{bot_role}'")
        
        response_text = f"좋아! 지금부터 너는 '{user_role}', 나는 '{bot_role}'이야. 역할에 맞춰 이야기해보자!"
        return response_text, chatroom_id

    async def talk(self, req: dict, profile_id: int, chatroom_id: int):
        user_input = req['user_input']
        session_id = req['session_id']
        session_state = self.db_manager.store.get(session_id)

        user_role, bot_role = None, None
        if session_state and session_state.get('roleplay_state'):
            state = session_state['roleplay_state']
            user_role = state.get('user_role')
            bot_role = state.get('bot_role')

        # --- 여기가 수정된 핵심 로직입니다 ---
        # 1. 중단 키워드가 있는지 먼저 확인
        if any(keyword in user_input for keyword in STOP_KEYWORDS):
            await self.db_manager.summarize_and_close_room(session_id)
            return {
                "type": "end",
                "response": "알겠어! 역할놀이를 종료할게. 재미있었어!",
                "user_role": user_role,
                "bot_role": bot_role
            }

        if not session_state or not session_state.get('roleplay_state'):
            return {"type": "error", "response": "역할놀이가 시작되지 않았습니다. 먼저 역할놀이를 시작해주세요."}

        if not self.conversational_chain:
            return {"type": "error", "response": "챗봇 로직 초기화에 실패했습니다."}

        role_instructions = ROLE_PROMPTS.get(bot_role, "주어진 역할에 충실하게 응답하세요.")
        system_prompt_text = f"""
# 역할극 미션: 완벽한 몰입

## 1. 페르소나 설정
- **당신의 역할:** {bot_role}
- **상대방(사용자)의 역할:** {user_role}
---

## 2. 핵심 연기 지침 (가장 중요)
### 2-1. 역할과 관계에 맞는 언어 사용
당신의 역할({bot_role})과 상대방 역할({user_role})의 관계를 파악하고, 그에 맞는 호칭과 언어(존댓말/반말)를 완벽하게 사용합니다.
예를 들어 당신의 역할이 선생님, 사용자의 역할이 학생이라면 존댓말을 사용하지 않습니다.

### 2-2. 완벽한 문장 구사
문법 오류, 특히 **조사(은/는, 이/가)와 맞춤법 오류가 절대 없도록** 가장 자연스러운 한국어 문장을 구사합니다.

### 2-3. 전문성 조절
역할에 맞는 지식을 활용하되, **절대 전문 용어를 남발하거나 상대방이 이해하기 어려운 수준으로 말하지 않습니다.** 대화의 목적은 지식 전달이 아닌 역할 연기입니다.

---

## 3. 절대 규칙
- **응답 길이:** 반드시 **1~2개의 문장**으로만 간결하게 응답합니다.
- **정체성 비밀:** 당신이 AI라거나, 이 미션을 수행 중이라는 사실을 절대 드러내지 않습니다.
- **상대방 언급 금지:** 최대한 상대방을 언급하지 마세요. (환자님). 본론만 이야기하세요.
- **전문성 조절:** 절대 전문 용어를 남발하거나 상대방이 이해하기 어려운 수준으로 말하지 않습니다. 대화의 목적은 지식 전달이 아닌 역할 연기입니다.
- **친구처럼 말하기**: 너는 선생님이므로, 반드시 완벽하고 자연스러운 한국어 **반말**을 사용한다. 절대로 '~요', '~습니다' 같은 존댓말을 쓰거나, AI, 챗봇처럼 말하지 않는다.


## 3. 마지막 확인
- 응답 길이 2개 이하 문장
- 전문성 답변 제외
- **반말 사용** 
"""

        try:
            response_text = await self.conversational_chain.ainvoke(
                {"input": user_input, "system_prompt": system_prompt_text},
                config={'configurable': {'session_id': session_id}}
            )
            return {
                "type": "continue",
                "response": response_text,
                "user_role": user_role,
                "bot_role": bot_role
            }
        except Exception as e:
            print(f"[오류] 역할놀이 대화 생성 중 문제 발생: {e}")
            return {"type": "error", "response": "미안, 지금은 대답하기가 좀 힘들어."}