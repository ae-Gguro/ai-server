import uvicorn
from pyngrok import ngrok, conf
import threading
import time
import os
import subprocess
import platform
from dotenv import load_dotenv

def kill_process_on_port(port):
    """지정된 포트를 사용하고 있는 프로세스를 찾아 종료합니다."""
    if platform.system() == "Windows":
        command = f"netstat -aon | findstr :{port}"
        try:
            output = subprocess.check_output(command, shell=True, text=True, stderr=subprocess.PIPE)
            for line in output.strip().split("\n"):
                if "LISTENING" in line:
                    parts = line.split()
                    pid = parts[-1]
                    print(f"✅ 포트 {port}를 사용 중인 프로세스(PID: {pid})를 종료합니다.")
                    subprocess.run(f"taskkill /PID {pid} /F", shell=True, check=True)
                    return
            print(f"✅ 포트 {port}가 이미 비어있습니다.")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"✅ 포트 {port}를 사용하는 프로세스가 없습니다.")
    else: # macOS / Linux
        command = f"lsof -ti :{port}"
        try:
            output = subprocess.check_output(command, shell=True, text=True, stderr=subprocess.PIPE)
            pids = output.strip().split("\n")
            if pids and pids[0]:
                print(f"✅ 포트 {port}를 사용 중인 프로세스(PID: {', '.join(pids)})를 종료합니다.")
                subprocess.run(f"kill -9 {' '.join(pids)}", shell=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"✅ 포트 {port}를 사용하는 프로세스가 없습니다.")


def run_fastapi():
    """FastAPI 서버를 실행하는 함수"""
    # --- 여기가 수정된 부분입니다 ---
    # reload=True 옵션을 제거하여 스레드 충돌을 방지합니다.
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000)

if __name__ == "__main__":
    load_dotenv()

    NGROK_AUTHTOKEN = os.getenv("NGROK_AUTHTOKEN")
    if NGROK_AUTHTOKEN:
        ngrok.set_auth_token(NGROK_AUTHTOKEN)
    else:
        print("⚠️ [경고] .env 파일에 NGROK_AUTHTOKEN이 설정되지 않았습니다.")

    conf.get_default().region = "ap"

    kill_process_on_port(8000)
    try:
        for tunnel in ngrok.get_tunnels():
            ngrok.disconnect(tunnel.public_url)
        print("✅ 기존 ngrok 터널을 정리했습니다.")
    except Exception:
        pass

    server_thread = threading.Thread(target=run_fastapi)
    server_thread.start()
    print("⏳ FastAPI 서버 시작 중...")

    time.sleep(5)

    try:
        public_url = ngrok.connect(8000)
        print("="*60)
        print(f"🚀 FastAPI 서버가 실행 중입니다.")
        print(f"✅ 외부 접속 공개 주소: {public_url}")
        print("="*60)
        server_thread.join()
    except Exception as e:
        print(f"❌ ngrok 연결 중 오류 발생: {e}")
    finally:
        print("\nShutting down servers...")
        ngrok.kill()