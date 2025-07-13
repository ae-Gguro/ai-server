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
        self.quizzes_by_topic = self._load_quiz_data(QUIZ_DATA_PATH)
        self.quiz_eval_chain = self._create_quiz_eval_chain()

    def _load_quiz_data(self, file_path):
        quizzes_by_topic = {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f: content = f.read()
            quiz_blocks = [block for block in content.strip().split('#---') if block.strip()]
            
            for block in quiz_blocks:
                lines = block.strip().split('\n')
                quiz_item = {}
                for line in lines:
                    if line.startswith('주제:'): quiz_item['topic'] = line.replace('주제:', '').strip()
                    elif line.startswith('질문:'): quiz_item['question'] = line.replace('질문:', '').strip()
                    elif line.startswith('정답:'): quiz_item['answer'] = line.replace('정답:', '').strip()
                    elif line.startswith('힌트:'): quiz_item['hint'] = line.replace('힌트:', '').strip()

                if all(k in quiz_item for k in ['topic', 'question', 'answer', 'hint']):
                    topic = quiz_item['topic']
                    quizzes_by_topic.setdefault(topic, []).append(quiz_item)

            if quizzes_by_topic:
                print(f"주제별 퀴즈 데이터 로드 성공: 총 {len(quizzes_by_topic)}개 주제")
                return quizzes_by_topic
            else:
                print(f"[경고] 퀴즈 파일({file_path})에서 유효한 퀴즈를 찾지 못했습니다.")
                return {}
        except Exception as e:
            print(f"[오류] 퀴즈 데이터 처리 중 문제 발생: {e}")
            return {}
    
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
            topic = req.get('topic')
            if not topic:
                return {"status": "error", "message": "퀴즈 주제를 알려주세요! (예: 횡단보도, 낯선 사람)", "chatroom_id": None}

            quiz_list = self.quizzes_by_topic.get(topic)
            if not quiz_list or len(quiz_list) < 5:
                return {"status": "error", "message": f"'{topic}'에 대한 퀴즈가 아직 부족해요. 다른 주제를 말해줄래?", "chatroom_id": None}
            
            selected_quizzes = random.sample(quiz_list, 5)
            
            chatroom_id = await self.db_manager.create_new_chatroom(session_id, profile_id, 'quiz')
            
            session_state['quiz_state'] = {
                'topic': topic,
                'questions': selected_quizzes,
                'current_step': 0,
                'attempts': 0
            }
            current_question = selected_quizzes[0]
            
            return {
                "status": "start",
                "step": 1,
                "message": f"좋아, '{topic}'에 대한 안전 퀴즈 시간!\n\n{current_question['question']}",
                "chatroom_id": chatroom_id
            }

        current_step_index = quiz_state['current_step']
        current_question = quiz_state['questions'][current_step_index]
        
        eval_result_text = await self.quiz_eval_chain.ainvoke({"answer": current_question['answer'], "user_input": user_input})
        is_correct = "[판단: 참]" in eval_result_text
        
        if is_correct:
            quiz_state['current_step'] += 1
            quiz_state['attempts'] = 0
            
            if quiz_state['current_step'] < len(quiz_state['questions']):
                next_question = quiz_state['questions'][quiz_state['current_step']]
                return {
                    "status": "start",
                    "step": quiz_state['current_step'] + 1,
                    "message": f"딩동댕! 정답이야! 다음 문제 나갑니다.\n\n{next_question['question']}",
                    "chatroom_id": session_state['chatroom_id']
                }
            else:
                await self.db_manager.summarize_and_close_room(session_id)
                return {
                    "status": "end",
                    "step": quiz_state['current_step'],
                    "message": "정답! 모든 퀴즈를 맞혔어, 정말 대단한걸? 또 다른 퀴즈를 풀고 싶으면 주제를 말해줘!",
                    "chatroom_id": None
                }
        else:
            quiz_state['attempts'] += 1
            if quiz_state['attempts'] < 2:
                return {
                    "status": "hint",
                    "step": quiz_state['current_step'] + 1,
                    "message": f"음... 조금 더 생각해볼까?\n힌트: {current_question['hint']}",
                    "chatroom_id": session_state['chatroom_id']
                }
            else:
                correct_answer_for_previous_question = current_question['answer']
                quiz_state['current_step'] += 1
                quiz_state['attempts'] = 0
                
                if quiz_state['current_step'] < len(quiz_state['questions']):
                    next_question = quiz_state['questions'][quiz_state['current_step']]
                    return {
                        "status": "answer_and_start",
                        "step": quiz_state['current_step'] + 1,
                        "message": f"아쉽다! 정답은 '{correct_answer_for_previous_question}'이었어. 다음 문제야!\n\n{next_question['question']}",
                        "chatroom_id": session_state['chatroom_id']
                    }
                else:
                    await self.db_manager.summarize_and_close_room(session_id)
                    return {
                        "status": "end",
                        "step": quiz_state['current_step'],
                        "message": f"아쉽다! 정답은 '{correct_answer_for_previous_question}'이었어. 이걸로 퀴즈가 모두 끝났어! 정말 수고했어!",
                        "chatroom_id": None
                    }