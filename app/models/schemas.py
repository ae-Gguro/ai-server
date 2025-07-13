from pydantic import BaseModel, Field
from typing import Optional

class ChatRequest(BaseModel):
    user_input: str
    session_id: str
    profile_id: int = 1

class RolePlayStartRequest(BaseModel):
    session_id: str
    profile_id: int = 1
    user_role: str
    bot_role: str

class AdviceRequest(BaseModel):
    profile_id: int

class EndRequest(BaseModel):
    session_id: str
    profile_id: int = 1

class FeedbackRequest(BaseModel):
    like: bool = Field(..., description="좋아요는 true, 싫어요는 false")

class QuizRequest(BaseModel):
    user_input: str
    session_id: str
    profile_id: int = 1
    topic: Optional[str] = None