from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
# from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.embeddings import OllamaEmbeddings
from app.db.database import DatabaseManager
from app.core.config import EMBEDDING_MODEL_NAME, RAG_DATA_PATH
from app.prompts.prompts import CONVERSATION_INSTRUCTION, TOPIC_CHECK_PROMPT_TEMPLATE

# 대화 중단을 감지하기 위한 키워드 리스트
STOP_KEYWORDS = ["그만", "끝", "종료", "이제 그만", "그만하고 싶어"]

class ConversationLogic:
    def __init__(self, model, db_manager: DatabaseManager):
        self.model = model
        self.db_manager = db_manager
        self.instruct = CONVERSATION_INSTRUCTION
        self.topic_check_chain = self._create_topic_check_chain()
        # self.rag_chain = self._setup_rag_and_history()
        self.conversational_chain = self._setup_conversational_chain()

        # RAG 관련 로직이 모두 제거된, 간단한 대화 체인 생성 함수
    def _setup_conversational_chain(self):
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", self.instruct),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
            ])
            chain = prompt | self.model | StrOutputParser()
            
            return RunnableWithMessageHistory(
                chain,
                self.db_manager._get_session_history,
                input_messages_key="input",
                history_messages_key="chat_history",
            )
        except Exception as e:
            print(f"[오류] 대화 체인 설정 중 문제 발생: {e}")
            return None

    def _create_topic_check_chain(self):
        try:
            prompt = ChatPromptTemplate.from_template(TOPIC_CHECK_PROMPT_TEMPLATE)
            return prompt | self.model | StrOutputParser()
        except Exception as e:
            print(f"[오류] 주제 분석 체인 생성 중 문제 발생: {e}"); return None

    # def _setup_rag_and_history(self):
    #     try:
    #         # embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
    #         embeddings = OllamaEmbeddings(model="mxbai-embed-large")
    #         documents = TextLoader(RAG_DATA_PATH, encoding='utf-8').load()
    #         text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    #         docs = text_splitter.split_documents(documents)
    #         retriever = Chroma.from_documents(docs, embeddings).as_retriever()
    #         prompt = ChatPromptTemplate.from_messages([
    #             ("system", f"{self.instruct}\n\n[참고할 만한 정보]\n{{context}}"),
    #             MessagesPlaceholder(variable_name="chat_history"),
    #             ("human", "{input}"),
    #         ])
    #         rag_chain_main = (RunnablePassthrough.assign(context=lambda x: retriever.get_relevant_documents(x["input"]))| prompt| self.model| StrOutputParser())
    #         return RunnableWithMessageHistory(rag_chain_main, self.db_manager._get_session_history, input_messages_key="input", history_messages_key="chat_history")
    #     except Exception as e:
    #         print(f"[오류] RAG 또는 체인 설정 중 심각한 문제 발생: {e}"); return None

    async def talk(self, req: dict, profile_id: int):
        user_input = req['user_input']
        session_id = req['session_id']

        # --- 여기가 수정된 핵심 로직입니다 ---
        # 1. 중단 키워드가 있는지 먼저 확인
        if any(keyword in user_input for keyword in STOP_KEYWORDS):
            await self.db_manager.summarize_and_close_room(session_id)
            return {
                "type": "end",
                "response": "오늘도 재밌었어! 다음에 또 이야기하자~"
            }

        session_state = self.db_manager.store.setdefault(session_id, {})
        current_chatroom_id = session_state.get('chatroom_id')
        history = session_state.get('hisstory')

        if not current_chatroom_id:
            current_chatroom_id = await self.db_manager.create_new_chatroom(session_id, profile_id, 'conversation')
        elif history and history.messages:
            history_str = "\n".join([f"{msg.type}: {msg.content}" for msg in history.messages[-4:]])
            topic_check_result = await self.topic_check_chain.ainvoke({"history": history_str, "input": user_input})
            if "NEW_TOPIC" in topic_check_result:
                await self.db_manager.summarize_and_close_room(session_id)
                current_chatroom_id = await self.db_manager.create_new_chatroom(session_id, profile_id, 'conversation')
        
        if not current_chatroom_id:
            return {"type": "error", "response": "채팅방을 만들거나 찾는 데 문제가 발생했어요."}

        if not self.rag_chain:
            return {"type": "error", "response": "챗봇 로직 초기화에 실패했습니다."}
            
        try:
            response_text = await self.rag_chain.ainvoke(
                {"input": user_input},
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