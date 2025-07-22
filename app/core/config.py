import os
from dotenv import load_dotenv

# .env 파일에서 환경 변수를 불러옵니다.
load_dotenv()

# --- DB 설정 ---
DB_CONFIG = {
    'dbname': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT')
}

# --- 모델 설정 ---
MODEL_NAME = os.getenv('MODEL_NAME')
EMBEDDING_MODEL_NAME = os.getenv('EMBEDDING_MODEL_NAME')

# --- 파일 경로 ---
QUIZ_DATA_PATH = os.getenv('QUIZ_DATA_PATH')
RAG_DATA_PATH = os.getenv('RAG_DATA_PATH')

# --- JWT 설정 (여기에 추가) ---
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")