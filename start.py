import os
import sys
import uvicorn
import threading
from pyngrok import ngrok, conf
import asyncio
from dotenv import load_dotenv

# --- 1. 경로 설정 및 .env 파일 로드 ---
project_path = '/content/drive/MyDrive/ai-server' #### 자기 경로에 맞게 .env 파일이 로드될 위치 지정하기
os.chdir(project_path)
sys.path.insert(0, project_path)
load_dotenv()

# --- 2. ngrok 인증 ---
NGROK_AUTH_TOKEN = "2Y4Va84bUn6RqQZ2f8w2IKm1czF_6gzKs8tYC5E51xGMPX5eA" #### AUTH KEY에 꼭 자신의 토큰 넣어주기!!!!!!
ngrok.set_auth_token(NGROK_AUTH_TOKEN)
conf.get_default().region = "ap"

# --- 3. FastAPI 서버 실행 ---
def run_fastapi():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_config=None)

# 4. 기존 8000번 포트 프로세스 종료
# fuser 명령어로 8000/tcp 포트를 사용하는 프로세스를 찾아 종료(-k)합니다.
get_ipython().system('fuser -k 8000/tcp')
print("✅ 기존 8000번 포트 프로세스를 정리했습니다.")
# ------------------------------------

# 5. 이전 ngrok 터널 종료
try:
    all_tunnels = ngrok.get_tunnels()
    for tunnel in all_tunnels:
        ngrok.disconnect(tunnel.public_url)
except Exception: pass

# 6. 스레드에서 서버 실행
server_thread = threading.Thread(target=run_fastapi)
server_thread.start()

import time
time.sleep(15)

# 7. ngrok 연결
public_url = ngrok.connect(8000)
print("="*60)
print("🚀 FastAPI 서버가 아래 공개 주소에서 실행 중입니다!")
print(public_url)
print("="*60)