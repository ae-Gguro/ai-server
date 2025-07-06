import asyncio
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.db.database import DatabaseManager
from app.prompts.prompts import SINGLE_NEGATIVE_TALK_ANALYSIS_PROMPT

class SentimentAnalyzer:
    def __init__(self, model, db_manager: DatabaseManager):
        self.model = model
        self.db_manager = db_manager
        # 단일 대화 분석을 위한 새로운 체인을 생성
        self.analysis_chain = self._create_analysis_chain()

    def _create_analysis_chain(self):
        prompt = ChatPromptTemplate.from_template(SINGLE_NEGATIVE_TALK_ANALYSIS_PROMPT)
        return prompt | self.model | StrOutputParser()

    async def analyze_individual_negative_talks(self, profile_id: int):
        # DB에서 부정적인 대화 목록 전체 조회 
        talks = self.db_manager.get_negative_talks_by_profile_id(profile_id)
        if not talks:
            return {"analyses": []} # 분석할 내용이 없으면 빈 리스트 반환

        # 각 대화를 개별적으로 분석하는 태스크 목록 생성 
        tasks = []
        for talk in talks:
            tasks.append(self.analysis_chain.ainvoke({"user_talk": talk['content']}))

        # 모든 분석 태스크를 병렬로 실행하여 결과를 받음 
        analysis_results = await asyncio.gather(*tasks)

        # 원본 대화 내용과 분석 결과를 합쳐서 최종 리스트 생성 
        final_analyses = []
        for i, talk in enumerate(talks):
            raw_analysis = analysis_results[i].strip()

            # LLM이 출력한 결과에서 원하는 문장만 추출
            clean_analysis = raw_analysis
            # '[출력 형식]'이라는 글자가 포함된 경우, 그 뒷부분만 가져옴 
            if "[출력 형식]" in raw_analysis:
                clean_analysis = raw_analysis.split("[출력 형식]")[-1].strip()
            # 그 외의 경우, 여러 줄일 경우 마지막 줄만 가져옴 
            elif ['\n', '\n\n'] in raw_analysis:
                 clean_analysis = raw_analysis.split('\n')[-1].strip()

            # 최종 결과에 content를 제외하고 talk_id와 analysis만 포함합니다.
            final_analyses.append({
                "talk_id": talk['id'],
                "analysis": clean_analysis
            })

        return {"analyses": final_analyses}