from langchain_ollama import ChatOllama
from app.core.config import MODEL_NAME
from app.db.database import DatabaseManager
from app.services.conversation_logic import ConversationLogic
from app.services.roleplay_logic import RolePlayLogic
from app.services.quiz_logic import QuizLogic
from app.services.relationship_advisor import RelationshipAdvisor

class ChatbotSystem:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ChatbotSystem, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, 'initialized'):
            return
        
        print("🤖 챗봇 시스템 로딩 시작...")
        self.model = ChatOllama(model=MODEL_NAME)
        self.db_manager = DatabaseManager(self.model)
        self.conversation_logic = ConversationLogic(self.model, self.db_manager)
        self.roleplay_logic = RolePlayLogic(self.model, self.db_manager)
        self.quiz_logic = QuizLogic(self.model, self.db_manager)
        self.relationship_advisor = RelationshipAdvisor(self.model)
        self.initialized = True
        print("✅ 챗봇 시스템이 정상적으로 로드되었습니다.")

chatbot_system = ChatbotSystem()