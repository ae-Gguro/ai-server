from fastapi import APIRouter, Depends
from app.models.schemas import EndRequest, AdviceRequest
from app.services.chatbot_system import chatbot_system
from app.core.security import get_current_user_id

router = APIRouter()

@router.post("/conversation/end", summary="대화 종료 및 요약")
async def end_conversation(
    req: EndRequest,
    user_id: int = Depends(get_current_user_id)
):
    await chatbot_system.db_manager.summarize_and_close_room(req.session_id)
    return {"message": "대화가 종료되고 요약되었습니다."}

@router.post("/relationship-advice", summary="관계 조언 생성")
async def get_relationship_advice(
    req: AdviceRequest,
    user_id: int = Depends(get_current_user_id)
):
    # --- 여기가 수정된 부분입니다 ---
    # generate_advice -> generate_weekly_report 로 함수 이름 변경
    # 또한, 서비스 함수는 profile_id만 필요로 하므로 req.profile_id만 전달합니다.
    return await chatbot_system.relationship_advisor.generate_advice(user_id, req.profile_id)