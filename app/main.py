from fastapi import FastAPI
from app.api.router import api_router
from app.services.chatbot_system import chatbot_system # This will initialize the system

app = FastAPI(title="꾸로 API (모듈 분리 버전)")

app.include_router(api_router)

@app.get("/", summary="루트 경로 확인")
def read_root():
    return {"Hello": "Welcome to Gguro Chatbot API"}