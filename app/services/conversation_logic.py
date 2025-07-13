from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_huggingface import HuggingFaceEmbeddings
from app.db.database import DatabaseManager
from app.core.config import EMBEDDING_MODEL_NAME, RAG_DATA_PATH
from app.prompts.prompts import CONVERSATION_INSTRUCTION, TOPIC_CHECK_PROMPT_TEMPLATE

class ConversationLogic:
    def __init__(self, model, db_manager: DatabaseManager):
        self.model = model
        self.db_manager = db_manager
        self.instruct = CONVERSATION_INSTRUCTION # 프롬프트 파일에서 가져옴
        self.topic_check_chain = self._create_topic_check_chain()
        self.rag_chain = self._setup_rag_and_history()

    def _create_topic_check_chain(self):
        try:
            prompt = ChatPromptTemplate.from_template(TOPIC_CHECK_PROMPT_TEMPLATE)
            return prompt | self.model | StrOutputParser()
        except Exception as e:
            print(f"[오류] 주제 분석 체인 생성 중 문제 발생: {e}"); return None

    def _setup_rag_and_history(self):
        try:
            embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
            documents = TextLoader(RAG_DATA_PATH, encoding='utf-8').load()
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
            docs = text_splitter.split_documents(documents)
            retriever = Chroma.from_documents(docs, embeddings).as_retriever()
            prompt = ChatPromptTemplate.from_messages([
                ("system", f"{self.instruct}\n\n[참고할 만한 정보]\n{{context}}"),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
            ])
            rag_chain_main = (
                RunnablePassthrough.assign(context=lambda x: retriever.get_relevant_documents(x["input"]))
                | prompt
                | self.model
                | StrOutputParser()
            )            
            return RunnableWithMessageHistory(rag_chain_main, self.db_manager._get_session_history, input_messages_key="input", history_messages_key="chat_history")
        except Exception as e:
            print(f"[오류] RAG 또는 체인 설정 중 심각한 문제 발생: {e}"); return None

    async def talk(self, req: dict, profile_id: int):
        user_input = req['user_input']
        session_id = req['session_id']
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
                current_chatroom_id = await self.db_manager.create_new_chatroom(session_id, profile_id, 'conversation')
        
        if not current_chatroom_id:
            return "채팅방을 만들거나 찾는 데 문제가 발생했어요.", None

        if not self.rag_chain:
            return "챗봇 로직 초기화에 실패했습니다.", current_chatroom_id
            
        try:
            response = await self.rag_chain.ainvoke(
                {"input": user_input},
                config={'configurable': {'session_id': session_id}}
            )
            return response, current_chatroom_id
        except Exception as e:
            print(f"[오류] 일상 대화 생성 중 문제 발생: {e}")
            return "미안, 지금은 대답하기가 좀 힘들어.", current_chatroom_id