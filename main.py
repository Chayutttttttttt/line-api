"""FastAPI application entry point."""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from components.line import router as line_router
from components.login import router as auth_router
from config import CORS_ORIGINS, PORT


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)
app.include_router(line_router)
app.include_router(auth_router)


if __name__ == "__main__":
    uvicorn.run(app, port=PORT, host="0.0.0.0")
