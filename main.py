"""Railway API with bounded input, request correlation and central error responses."""
import logging
import hashlib
import time
from collections import defaultdict, deque
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException

from components.acceptance import router as acceptance_router
from components.documents import router as document_router
from components.learning import router as learning_router
from components.line import router as line_router
from components.login import router as auth_router
from config import CORS_ORIGINS, MAX_UPLOAD_BYTES, PORT
from db.database import engine

app = FastAPI(title="LINE Learning API", version="0.3.0")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "Idempotency-Key"],
    expose_headers=["X-Request-ID", "Content-Disposition"])
recent = defaultdict(deque)


def error_response(request, status, code, message=None):
    return JSONResponse(status_code=status, content={"code": code, "message": message or code,
        "request_id": getattr(request.state, "request_id", str(uuid4()))})


@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.request_id = str(uuid4())
    # Per-process ingress protection; deployment-level limits should complement it.
    login_request = request.url.path == "/auth/line"
    authorization = request.headers.get("Authorization", "")
    identity = hashlib.sha256(authorization.encode()).hexdigest() if authorization.startswith("Bearer ") and not login_request else request.client.host if request.client else "unknown"
    key = (identity, login_request)
    now = time.monotonic()
    queue = recent[key]
    while queue and queue[0] < now - 60:
        queue.popleft()
    limit = 60 if key[1] else 180
    if len(queue) >= limit:
        return error_response(request, 429, "RATE_LIMITED")
    queue.append(now)
    if len(recent) > 10000:
        for old_key in list(recent):
            if not recent[old_key] or recent[old_key][-1] < now - 60:
                del recent[old_key]
    # Bound actual bytes even without Content-Length. Preserve signed raw webhook body.
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        body = bytearray()
        maximum = MAX_UPLOAD_BYTES + 65536 if request.url.path == "/documents" else 65536
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > maximum:
                return error_response(request, 413, "REQUEST_TOO_LARGE")
        request._body = bytes(body)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.exception_handler(HTTPException)
async def http_error(request, error):
    return error_response(request, error.status_code, str(error.detail))


@app.exception_handler(RequestValidationError)
async def validation_error(request, error):
    return error_response(request, 400, "INVALID_INPUT", "ตรวจรูปแบบข้อมูล วันเวลา และช่องที่จำเป็น")


@app.exception_handler(IntegrityError)
async def conflict_error(request, error):
    return error_response(request, 409, "DATA_CONFLICT")


@app.exception_handler(SQLAlchemyError)
async def database_error(request, error):
    logging.getLogger(__name__).error("database failure request=%s class=%s", request.state.request_id, type(error).__name__)
    return error_response(request, 503, "DATABASE_UNAVAILABLE")


@app.get("/health")
def health():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok"}


for router in (line_router, auth_router, document_router, learning_router, acceptance_router):
    app.include_router(router)


if __name__ == "__main__":
    uvicorn.run(app, port=PORT, host="0.0.0.0")
