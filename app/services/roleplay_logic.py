from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.output_parsers import StrOutputParser
from app.db.database import DatabaseManager
from app.prompts.prompts import ROLE_PROMPTS

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

        if not session_state or not session_state.get('roleplay_state'):
            return "역할놀이가 시작되지 않았습니다. 먼저 역할놀이를 시작해주세요.", None, None

        if not self.conversational_chain:
            return "챗봇 로직 초기화에 실패했습니다.", None, None

        state = session_state['roleplay_state']
        user_role = state['user_role']
        bot_role = state['bot_role']
        role_instructions = ROLE_PROMPTS.get(bot_role, "주어진 역할에 충실하게 응답하세요.")
        system_prompt_text = f"""[매우 중요한 지시]
당신의 신분은 '{bot_role}'입니다. 사용자는 '{user_role}' 역할을 맡고 있습니다.
다른 모든 지시사항보다 이 역할 설정을 최우선으로 여기고, 당신의 말투, 어휘, 태도 모두 '{bot_role}'에 완벽하게 몰입해서 응답해야 합니다.
[역할 상세 지침]
{role_instructions}
이제 '{bot_role}'로서 대화를 자연스럽게 시작하거나 이어나가세요."""

        try:
            response_text = await self.conversational_chain.ainvoke(
                {"input": user_input, "system_prompt": system_prompt_text},
                config={'configurable': {'session_id': session_id}}
            )
            # 응답 텍스트, 사용자 역할, 봇 역할을 튜플로 반환
            return response_text, user_role, bot_role
        except Exception as e:
            print(f"[오류] 역할놀이 대화 생성 중 문제 발생: {e}")
            # 오류 발생 시에도 역할 정보를 함께 반환
            return "미안, 지금은 대답하기가 좀 힘들어.", user_role, bot_role