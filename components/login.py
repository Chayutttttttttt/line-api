"""Line etc. Login"""

from fastapi import APIRouter,Response
from pydantic import BaseModel

router = APIRouter(prefix="/auth",tags=["auth"])

class Request(BaseModel):
    id_token: str

@router.post("/line")
async def line_login(data: Request,response: Response):
    id_token = data.id_token
    print(id_token, response)
