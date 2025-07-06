import uvicorn
import os

if __name__ == "__main__":
    # --- 환경 설정 ---

    os.environ['OLLAMA_MODELS'] = 'D:/ollama_models'
    os.environ['HF_HOME'] = 'D:/huggingface_models'
    
    print("🚀 FastAPI 서버를 시작합니다. http://127.0.0.1:8000/docs")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)