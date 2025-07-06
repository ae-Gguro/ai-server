## 꾸로(Gguro) AI 챗봇 API
**꾸로(Gguro)**는 아이들의 눈높이에 맞춰 상호작용하는 다정한 AI 친구입니다. 이 프로젝트는 아이들과의 다양한 대화(일상, 역할놀이, 퀴즈)를 통해 정서적 유대감을 형성하고, 부모님에게는 아이의 심리를 분석하여 관계 개선을 위한 조언을 제공하는 FastAPI 기반의 백엔드 서비스입니다.

✨ 주요 기능
- 일상 대화: 아이의 일상적인 질문에 친절하고 상냥하게 답변하며 대화를 이끌어갑니다.

- 역할놀이: 어부, 기사, 꼬마 등 다양한 역할에 몰입하여 아이의 상상력을 자극하는 대화를 제공합니다.

- 안전 퀴즈: 아이들이 꼭 알아야 할 안전 상식을 재미있는 퀴즈 형식으로 풀어봅니다.

- 대화 요약 및 관리: 대화 주제가 바뀔 때 자동으로 이전 대화를 요약하고, 세션을 관리하여 체계적인 기록을 남깁니다.

- 부모를 위한 관계 조언: 하루 동안 나눈 아이와의 대화를 분석하여 아이의 심리 상태와 관계 개선을 위한 구체적인 조언을 생성합니다.


## 🛠️ 기술 스택
Backend: FastAPI, Uvicorn

LLM: Ollama (Llama3-Korean)

Framework: Langchain

Database: PostgreSQL

Vector Store: ChromaDB

Embeddings: HuggingFace Embeddings

## 🚀 시작하기
1. 사전 요구사항
- Python 3.8 이상

- PostgreSQL 데이터베이스

- Ollama 및 timhan/llama3korean8b4qkm 모델 설치

2. 설치 및 설정
- 프로젝트 파일 준비
프로젝트 파일을 다운로드하거나 Git을 통해 복제합니다.

- 필요 패키지 설치
프로젝트 최상위 폴더에서 아래 명령어를 실행합니다.

```Bash
pip install -r requirements.txt
```
환경변수 및 설정

run.py 파일에서 Ollama 및 HuggingFace 모델이 저장된 로컬 경로를 설정합니다.

```Python
os.environ['OLLAMA_MODELS'] = 'D:/ollama_models' # 실제 경로로 수정
os.environ['HF_HOME'] = 'D:/huggingface_models'   # 실제 경로로 수정
```
app/core/config.py 파일에서 PostgreSQL 데이터베이스 연결 정보를 수정합니다.

3. 서버 실행
아래 명령어를 통해 FastAPI 서버를 시작합니다.

```Bash
python run.py
```
서버가 정상적으로 실행되면, 웹 브라우저에서 http://127.0.0.1:8000/docs 로 접속하여 API 문서를 확인할 수 있습니다.



## 📖 API 엔드포인트
서버 실행 후 Swagger UI에서 모든 API의 상세 명세를 확인하고 직접 테스트해볼 수 있습니다.

- `/conversation/talk`: 일상 대화

- `/roleplay/start`: 역할놀이 시작

- `/roleplay/talk`: 역할놀이 대화

- `/quiz/talk`: 퀴즈 시작 및 답변 제출

- `/relationship-advice:` 부모를 위한 관계 조언 생성

- `/conversation/end`: 현재 대화 세션 강제 종료 및 요약



📂 프로젝트 구조
```
gguro_chatbot/
├── app/
│   ├── main.py             # FastAPI 앱 초기화
│   ├── api/                # API 라우터 및 엔드포인트
│   ├── core/               # 핵심 설정 (DB 정보 등)
│   ├── db/                 # 데이터베이스 관리 로직
│   ├── models/             # Pydantic 스키마
│   ├── prompts/            # 모든 LLM 프롬프트
│   └── services/           # 비즈니스 로직 (대화, 퀴즈, 역할놀이 등)
├── rag_data/               # RAG 및 퀴즈 데이터
├── requirements.txt        # 필요 패키지 목록
└── run.py                  # 서버 실행 스크립트
```

