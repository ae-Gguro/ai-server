from pydantic import BaseModel

class ChatRequest(BaseModel):
    user_input: str
    session_id: str
    profile_id: int = 1

class RolePlayRequest(ChatRequest):
    user_role: str
    bot_role: str

class AdviceRequest(BaseModel):
    profile_id: int

class EndRequest(BaseModel):
    session_id: str
    profile_id: int = 1