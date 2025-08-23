import random
import asyncio
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.db.database import DatabaseManager
from app.prompts.prompts import QUIZ_EVAL_SYSTEM_PROMPT, QUIZ_EVAL_FEW_SHOTS # 안전 퀴즈의 평가 프롬프트 재사용

class AnimalQuizLogic:
    def __init__(self, model, db_manager: DatabaseManager):
        self.model = model
        self.db_manager = db_manager
        self.quizzes_by_animal = self._load_quiz_data("rag_data/animal_quiz_data.txt")
        self.quiz_eval_chain = self._create_quiz_eval_chain()

    def _load_quiz_data(self, file_path):
        quizzes_by_animal = {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f: content = f.read()
            quiz_blocks = [block for block in content.strip().split('#---') if block.strip()]
            for block in quiz_blocks:
                quiz_item = {}
                for line in block.strip().split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        quiz_item[key.strip()] = value.strip()
                if all(k in quiz_item for k in ['주제', '질문', '정답', '힌트']):
                    animal_name = quiz_item['주제']
                    quizzes_by_animal.setdefault(animal_name, []).append(quiz_item)
            print(f"동물 퀴즈 데이터 로드 성공: 총 {len(quizzes_by_animal)}종류 동물")
            return quizzes_by_animal
        except Exception as e:
            print(f"[오류] 동물 퀴즈 데이터 로드 실패: {e}")
            return {}

    def _create_quiz_eval_chain(self):
        # 안전 퀴즈와 동일한 평가 체인을 사용
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", QUIZ_EVAL_SYSTEM_PROMPT), 
                *sum([[("human", ex["input"]), ("ai", ex["output"])] for ex in QUIZ_EVAL_FEW_SHOTS], []), 
                ("human", "핵심 개념: {answer}\n답변: {user_input}")
            ])
            return prompt | self.model | StrOutputParser()
        except Exception as e: 
            print(f"[오류] 동물 퀴즈 채점 체인 생성 실패: {e}"); return None

    async def talk(self, req: dict, user_id: int, profile_id: int):
        user_input = req['user_input']
        session_id = req['session_id']
        animal_name = req.get('animal_name')
        
        session_state = self.db_manager.store.setdefault(session_id, {})
        quiz_state = session_state.get('animal_quiz')

        if not quiz_state: # 퀴즈 시작
            if not animal_name:
                return {"status": "error", "message": "어떤 동물 퀴즈를 시작할까요?"}
            
            quiz_list = self.quizzes_by_animal.get(animal_name)
            if not quiz_list or len(quiz_list) < 5:
                return {"status": "error", "message": f"'{animal_name}'에 대한 퀴즈가 아직 부족해요."}

            selected_quizzes = random.sample(quiz_list, 5)
            chatroom_id = await self.db_manager.create_new_chatroom(session_id, profile_id, 'animal_quiz')
            
            session_state['animal_quiz'] = {
                'questions': selected_quizzes, 'current_step': 0, 'attempts': 0, 'score': 0
            }
            
            first_question = selected_quizzes[0]
            return {
                "status": "start",
                "step": 1,
                "message": f"좋아, '{animal_name}'에 대한 동물 퀴즈 시간이야!\n\n{first_question['질문']}",
                "chatroom_id": chatroom_id
            }

        # 퀴즈 진행 (답변 처리)
        current_q = quiz_state['questions'][quiz_state['current_step']]
        eval_result_text = await self.quiz_eval_chain.ainvoke({"answer": current_q['정답'], "user_input": user_input})
        is_correct = "[판단: 참]" in eval_result_text

        if is_correct:
            quiz_state['score'] += 1
            quiz_state['current_step'] += 1
            quiz_state['attempts'] = 0
            
            if quiz_state['current_step'] < len(quiz_state['questions']):
                next_q = quiz_state['questions'][quiz_state['current_step']]
                return {
                    "status": "start",
                    "step": quiz_state['current_step'] + 1,
                    "message": f"딩동댕! 정답이야! 다음 문제!\n\n{next_q['질문']}",
                    "chatroom_id": session_state['chatroom_id']
                }
            else:
                final_score = quiz_state['score']
                total = len(quiz_state['questions'])
                await self.db_manager.summarize_and_close_room(session_id)
                return {
                    "status": "end",
                    "score": f"{final_score}/{total}",
                    "message": f"대단해! 모든 동물 퀴즈를 풀었어!\n오늘의 점수: {final_score}/{total}",
                    "chatroom_id": None
                }
        else: # 오답
            quiz_state['attempts'] += 1
            if quiz_state['attempts'] < 2:
                return {
                    "status": "hint",
                    "step": quiz_state['current_step'] + 1,
                    "message": f"'{user_input}'(은)는 정답이 아니야. 힌트를 잘 보고 다시 생각해볼까?\n힌트: {current_q['힌트']}",
                    "chatroom_id": session_state['chatroom_id']
                }
            else:
                correct_answer = current_q['정답']
                quiz_state['current_step'] += 1
                quiz_state['attempts'] = 0
                
                if quiz_state['current_step'] < len(quiz_state['questions']):
                    next_q = quiz_state['questions'][quiz_state['current_step']]
                    return {
                        "status": "answer_and_start",
                        "step": quiz_state['current_step'] + 1,
                        "message": f"아쉽다! 정답은 '{correct_answer}'이었어. 다음 문제야!\n\n{next_q['질문']}",
                        "chatroom_id": session_state['chatroom_id']
                    }
                else:
                    final_score = quiz_state['score']
                    total = len(quiz_state['questions'])
                    await self.db_manager.summarize_and_close_room(session_id)
                    return {
                        "status": "end",
                        "score": f"{final_score}/{total}",
                        "message": f"아쉽다! 정답은 '{correct_answer}'이었어. 이걸로 퀴즈가 모두 끝났어!\n오늘의 점수: {final_score}/{total}",
                        "chatroom_id": None
                    }