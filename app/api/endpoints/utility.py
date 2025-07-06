from fastapi import APIRouter
from app.models.schemas import EndRequest, AdviceRequest
from app.services.chatbot_system import chatbot_system

router = APIRouter()

@router.post("/conversation/end", summary="대화 종료 및 요약")
async def end_conversation(req: EndRequest):
    await chatbot_system.db_manager.summarize_and_close_room(req.session_id)
    return {"message": "대화가 종료되고 요약되었습니다."}

@router.post("/relationship-advice", summary="관계 조언 생성")
async def get_relationship_advice(req: AdviceRequest):
    return await chatbot_system.relationship_advisor.generate_advice(req.dict())