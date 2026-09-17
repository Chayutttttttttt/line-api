"""Receive a LIFF ID token for the temporary login connection test."""

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

router = APIRouter(prefix="/auth", tags=["auth"])

class Request(BaseModel):
    id_token: str = Field(min_length=1)

@router.post("/line")
async def line_login(data: Request, res: Response):
    id_token = data
    # Temporary debugging only: this does not verify the token or create a session.
    print(id_token, res, flush=True)
    return {"received": True}
