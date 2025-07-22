FROM python:3.11.1

# 시간대 설정
ENV TZ=Asia/Seoul
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 작업 디렉토리 생성
WORKDIR /app

# requirements 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 앱 소스 복사
COPY ./app ./app

# 퀴즈 및 RAG에 필요한 데이터 폴더
COPY ./rag_data ./rag_data

# 포트 노출
EXPOSE 8000

# 실행 명령
ENTRYPOINT ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]