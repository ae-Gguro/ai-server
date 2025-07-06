import random
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.db.database import DatabaseManager
from app.core.config import QUIZ_DATA_PATH
from app.prompts.prompts import QUIZ_EVAL_SYSTEM_PROMPT, QUIZ_EVAL_FEW_SHOTS

class QuizLogic:
    def __init__(self, model, db_manager: DatabaseManager):
        self.model = model
        self.db_manager = db_manager
        self.quiz_data = self._load_quiz_data(QUIZ_DATA_PATH)
        self.quiz_eval_chain = self._create_quiz_eval_chain()

    def _load_quiz_data(self, file_path):
        quizzes = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f: content = f.read()
            quiz_blocks = [block for block in content.strip().split('#---') if block.strip()]
            for block in quiz_blocks:
                lines = block.strip().split('\n'); quiz_item = {}
                for line in lines:
                    if line.startswith('질문:'): quiz_item['question'] = line.replace('질문:', '').strip()
                    elif line.startswith('정답:'): quiz_item['answer'] = line.replace('정답:', '').strip()
                    elif line.startswith('힌트:'): quiz_item['hint'] = line.replace('힌트:', '').strip()
                if 'question' in quiz_item and 'answer' in quiz_item and 'hint' in quiz_item: quizzes.append(quiz_item)
            if quizzes: print(f"대화형 퀴즈 데이터 로드 성공: 총 {len(quizzes)}개"); return quizzes
            else: print(f"[경고] 퀴즈 파일({file_path})에서 유효한 퀴즈를 찾지 못했습니다."); return []
        except Exception as e: print(f"[오류] 퀴즈 데이터 처리 중 문제 발생: {e}"); return []
    
    def _create_quiz_eval_chain(self):
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", QUIZ_EVAL_SYSTEM_PROMPT), 
                *sum([[("human", ex["input"]), ("ai", ex["output"])] for ex in QUIZ_EVAL_FEW_SHOTS], []), 
                ("human", "핵심 개념: {answer}\n답변: {user_input}")
            ])
            return prompt | self.model | StrOutputParser()
        except Exception as e: 
            print(f"[오류] 퀴즈 채점 체인 생성 중 문제 발생: {e}"); return None
    
    async def talk(self, req: dict, profile_id: int):
        user_input = req['user_input']
        session_id = req['session_id']
        session_state = self.db_manager.store.setdefault(session_id, {})
        quiz_state = session_state.get('quiz_state')
        
        if not quiz_state:
            if not self.quiz_data: return "미안, 지금은 퀴즈를 낼 수 없어.", None
            chatroom_id = await self.db_manager.create_new_chatroom(session_id, profile_id, 'quiz')
            
            quiz = random.choice(self.quiz_data)
            session_state['quiz_state'] = {'quiz_item': quiz, 'attempts': 0}
            return f"좋아, 재미있는 안전 퀴즈 시간! \n\n{quiz['question']}", chatroom_id

        current_quiz = quiz_state['quiz_item']
        eval_result_text = await self.quiz_eval_chain.ainvoke({"answer": current_quiz['answer'], "user_input": user_input})
        is_correct = "[판단: 참]" in eval_result_text
        
        if is_correct:
            response = f"딩동댕! 정답이야! 정답은 바로... **{current_quiz['answer']}**\n\n정말 똑똑한걸? 또 퀴즈 풀고 싶으면 '퀴즈'라고 말해줘!"
            await self.db_manager.summarize_and_close_room(session_id)
            return response, None
        else:
            quiz_state['attempts'] += 1
            if quiz_state['attempts'] < 2:
                return f"음... 조금 더 생각해볼까? 힌트는 '{current_quiz['hint']}'이야. 다시 한번 생각해볼래?", session_state['chatroom_id']
            else:
                response = f"아쉽다! 정답은 '{current_quiz['answer']}'이었어. 괜찮아, 이렇게 하나씩 배우는 거지! 다음엔 꼭 맞힐 수 있을 거야."
                await self.db_manager.summarize_and_close_room(session_id)
                return response, None