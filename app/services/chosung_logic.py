import random
from app.db.database import DatabaseManager

class ChosungQuizLogic:
    CHOSUNG_LIST = ['ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.quiz_data = self._load_quiz_data("rag_data/chosung_quiz_data.txt")

    def _load_quiz_data(self, file_path):
        data = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        word, hint = line.strip().split(',', 1)
                        data.append({"word": word, "hint": hint})
            if data:
                print(f"초성 퀴즈 데이터 로드 성공: 총 {len(data)}개 단어")
            return data
        except Exception as e:
            print(f"[오류] 초성 퀴즈 데이터 로드 실패: {e}")
            return []

    def _get_chosung(self, text):
        chosung = ""
        for char in text.strip():
            if '가' <= char <= '힣':
                char_code = ord(char) - 44032
                chosung_index = char_code // (21 * 28)
                chosung += self.CHOSUNG_LIST[chosung_index]
        return chosung

    async def talk(self, req: dict, profile_id: int):
        user_input = req['user_input']
        session_id = req['session_id']
        session_state = self.db_manager.store.setdefault(session_id, {})
        chosung_quiz_state = session_state.get('chosung_quiz')

        # 1. 퀴즈 시작
        if not chosung_quiz_state:
            if not self.quiz_data or len(self.quiz_data) < 5:
                return {"status": "error", "message": "초성 퀴즈가 아직 부족해요. 다음에 다시 시도해줘!", "chatroom_id": None}
            
            selected_quizzes = random.sample(self.quiz_data, 5)
            
            chatroom_id = await self.db_manager.create_new_chatroom(session_id, profile_id, 'chosung_quiz')
            
            chosung = self._get_chosung(selected_quizzes[0]["word"])

            session_state['chosung_quiz'] = {
                'questions': selected_quizzes,
                'current_step': 0,
                'attempts': 0,
                'score': 0 
            }
            
            return {
                "status": "start",
                "step": 1,
                "message": f"좋아, 초성 퀴즈 시간이야!\n\n제시된 초성은 '{chosung}'이야. 힌트는 '{selected_quizzes[0]['hint']}'!",
                "chatroom_id": chatroom_id
            }

        # 2. 퀴즈 진행 중 (답변 처리)
        current_step_index = chosung_quiz_state['current_step']
        current_question = chosung_quiz_state['questions'][current_step_index]
        
        is_correct = (user_input.strip() == current_question["word"])
        
        # 정답
        if is_correct:
            chosung_quiz_state['score'] += 1
            chosung_quiz_state['current_step'] += 1
            chosung_quiz_state['attempts'] = 0
            
            if chosung_quiz_state['current_step'] < len(chosung_quiz_state['questions']):
                next_question = chosung_quiz_state['questions'][chosung_quiz_state['current_step']]
                next_chosung = self._get_chosung(next_question["word"])
                return {
                    "status": "start",
                    "step": chosung_quiz_state['current_step'] + 1,
                    "message": f"딩동댕! 정답이야! 다음 문제!\n\n초성은 '{next_chosung}', 힌트는 '{next_question['hint']}'이야.",
                    "chatroom_id": session_state['chatroom_id']
                }
            else:
                await self.db_manager.summarize_and_close_room(session_id)
                final_score = chosung_quiz_state['score']
                total_questions = len(chosung_quiz_state['questions'])
                return {
                    "status": "end",
                    "step": chosung_quiz_state['current_step'],
                    "score": f"{final_score}/{total_questions}",
                    "message": f"대단해! 오늘 준비된 단어를 다 풀었어!\n오늘의 점수: {final_score}/{total_questions}",
                    "chatroom_id": None
                }
        # 오답
        else:
            chosung_quiz_state['attempts'] += 1
            if chosung_quiz_state['attempts'] < 2:

                return {
                    "status": "hint",
                    "step": chosung_quiz_state['current_step'] + 1,
                    "message": f"'{user_input}'(은)는 정답이 아니야.\n다시 생각해볼까?",
                    "chatroom_id": session_state['chatroom_id']
                }
            else:
                correct_answer_for_previous_question = current_question['word']
                chosung_quiz_state['current_step'] += 1
                chosung_quiz_state['attempts'] = 0
                
                if chosung_quiz_state['current_step'] < len(chosung_quiz_state['questions']):
                    next_question = chosung_quiz_state['questions'][chosung_quiz_state['current_step']]
                    next_chosung = self._get_chosung(next_question["word"])
                    return {
                        "status": "answer_and_start",
                        "step": chosung_quiz_state['current_step'] + 1,
                        "message": f"아쉽다! 정답은 '{correct_answer_for_previous_question}'이었어. 다음 문제야!\n\n초성은 '{next_chosung}', 힌트는 '{next_question['hint']}'이야.",
                        "chatroom_id": session_state['chatroom_id']
                    }
                else:
                    await self.db_manager.summarize_and_close_room(session_id)
                    final_score = chosung_quiz_state['score']
                    total_questions = len(chosung_quiz_state['questions'])
                    return {
                        "status": "end",
                        "step": chosung_quiz_state['current_step'],
                        "score": f"{final_score}/{total_questions}",
                        "message": f"아쉽다! 정답은 '{correct_answer_for_previous_question}'이었어. 이걸로 퀴즈가 모두 끝났어!\n오늘의 점수: {final_score}/{total_questions}",
                        "chatroom_id": None
                    }