from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from app.db.database import DatabaseManager
from app.prompts.prompts import CONVERSATION_INSTRUCTION, TOPIC_CHECK_PROMPT_TEMPLATE
# from app.db.profile_manager import get_profile_name -> 이 줄은 필요 없습니다.

STOP_KEYWORDS = ["그만", "끝", "종료", "이제 그만", "그만하고 싶어"]

class ConversationLogic:
    def __init__(self, model, db_manager: DatabaseManager):
        self.model = model
        self.db_manager = db_manager
        self.instruct_template = CONVERSATION_INSTRUCTION
        self.topic_check_chain = self._create_topic_check_chain()
        self.conversational_chain = self._setup_conversational_chain()

    def _create_topic_check_chain(self):
        try:
            prompt = ChatPromptTemplate.from_template(TOPIC_CHECK_PROMPT_TEMPLATE)
            return prompt | self.model | StrOutputParser()
        except Exception as e:
            print(f"[오류] 주제 분석 체인 생성 실패: {e}"); return None

    def _setup_conversational_chain(self):
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
            print(f"[오류] 대화 체인 설정 중 문제 발생: {e}")
            return None

    async def talk(self, req: dict, user_id: int, profile_id: int):
        user_input = req['user_input']
        session_id = req['session_id']

        # --- 여기가 수정된 핵심 부분입니다 ---
        # self.db_manager를 통해 프로필 이름을 조회합니다.
        profile_name = self.db_manager.get_profile_name(profile_id)

        print(profile_name)
        
        if not profile_name:
            profile_name = "친구" # 조회 실패 시 기본값

        system_prompt_text = self.instruct_template.format(profile_name=profile_name)

        if any(keyword in user_input for keyword in STOP_KEYWORDS):
            end_message = f"알겠어, {profile_name}! 대화를 종료할게. 다음에 또 이야기하자!"
            await self.db_manager.summarize_and_close_room(session_id)
            return {"type": "end", "response": end_message}

        session_state = self.db_manager.store.setdefault(session_id, {})
        current_chatroom_id = session_state.get('chatroom_id')
        history = session_state.get('history')

        if not current_chatroom_id:
            current_chatroom_id = await self.db_manager.create_new_chatroom(session_id, profile_id, 'conversation')
        elif history and history.messages:
            history_str = "\n".join([f"{msg.type}: {msg.content}" for msg in history.messages[-4:]])
            topic_check_result = await self.topic_check_chain.ainvoke({"history": history_str, "input": user_input})
            if "NEW_TOPIC" in topic_check_result:
                await self.db_manager.summarize_and_close_room(session_id)
                current_chatroom_id = await self.db_manager.create_new_chatroom(session_id, user_id, profile_id, 'conversation')
        
        if not current_chatroom_id:
            return {"type": "error", "response": "채팅방을 만들거나 찾는 데 문제가 발생했어요."}

        if not self.conversational_chain:
            return {"type": "error", "response": "챗봇 로직 초기화에 실패했습니다."}
            
        try:
            response_text = await self.conversational_chain.ainvoke(
                {"input": user_input, "system_prompt": system_prompt_text},
                config={'configurable': {'session_id': session_id}}
            )
            return {
                "type": "continue",
                "response": response_text,
                "chatroom_id": current_chatroom_id
            }
        except Exception as e:
            print(f"[오류] 일상 대화 생성 중 문제 발생: {e}")
            return {"type": "error", "response": "미안, 지금은 대답하기가 좀 힘들어."}