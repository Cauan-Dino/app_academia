from pydantic import BaseModel, Field

class AtualizarPushToken(BaseModel):
    push_token: str = Field(..., pattern=r'^ExponentPushToken\[.+\]$')