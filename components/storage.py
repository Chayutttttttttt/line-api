"""Private file storage adapters. Object keys never come from client filenames."""
import hashlib
import os
from pathlib import Path
import re
import tempfile

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException

from config import FILE_STORAGE_ROOT, S3_BUCKET, S3_ENDPOINT_URL, S3_REGION, S3_ADDRESSING_STYLE, STORAGE_BACKEND

KEY_PATTERN = re.compile(r"[a-zA-Z0-9_/-]+\.[a-z0-9]+")


def object_path(key: str) -> Path:
    if not KEY_PATTERN.fullmatch(key) or ".." in key or key.startswith("/"):
        raise HTTPException(400, "INVALID_OBJECT_KEY")
    root = Path(FILE_STORAGE_ROOT).resolve()
    path = (root / key).resolve()
    if root not in path.parents:
        raise HTTPException(400, "INVALID_OBJECT_KEY")
    return path


def local_put(key: str, data: bytes):
    path = object_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replacement avoids serving partial files after a crash.
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def s3_client():
    if not S3_ENDPOINT_URL.startswith("https://") or not S3_BUCKET:
        raise HTTPException(503, "S3_STORAGE_NOT_CONFIGURED")
    return boto3.client("s3", endpoint_url=S3_ENDPOINT_URL, region_name=S3_REGION,
        config=Config(s3={"addressing_style": S3_ADDRESSING_STYLE},
            connect_timeout=10, read_timeout=30, retries={"max_attempts": 2}))


def put_file(key: str, data: bytes):
    if STORAGE_BACKEND == "s3":
        object_path(key)
        try:
            s3_client().put_object(Bucket=S3_BUCKET, Key=key, Body=data,
                ContentType="application/octet-stream")
        except (BotoCoreError, ClientError):
            raise HTTPException(503, "FILE_STORAGE_UNAVAILABLE") from None
    elif STORAGE_BACKEND == "local":
        local_put(key, data)
    else:
        raise HTTPException(503, "UNKNOWN_STORAGE_BACKEND")


def read_file(key: str, checksum: str) -> bytes:
    try:
        if STORAGE_BACKEND == "s3":
            body = s3_client().get_object(Bucket=S3_BUCKET, Key=key)["Body"]
            try:
                data = body.read()
            finally:
                body.close()
        elif STORAGE_BACKEND == "local":
            data = object_path(key).read_bytes()
        else:
            raise HTTPException(503, "UNKNOWN_STORAGE_BACKEND")
    except (BotoCoreError, ClientError):
        raise HTTPException(503, "FILE_STORAGE_UNAVAILABLE") from None
    except FileNotFoundError:
        raise HTTPException(404, "FILE_NOT_FOUND") from None
    if hashlib.sha256(data).hexdigest() != checksum:
        raise HTTPException(409, "FILE_CHECKSUM_MISMATCH")
    return data


def delete_file(key: str) -> None:
    """Permanently remove a single validated storage key (not a whole bucket).

    Missing files are treated as already deleted, so a partially completed
    document deletion can safely be retried.
    """
    if STORAGE_BACKEND == "s3":
        object_path(key)
        try:
            s3_client().delete_object(Bucket=S3_BUCKET, Key=key)
        except (BotoCoreError, ClientError):
            raise HTTPException(503, "FILE_STORAGE_DELETE_FAILED") from None
    elif STORAGE_BACKEND == "local":
        try:
            object_path(key).unlink(missing_ok=True)
        except OSError:
            raise HTTPException(503, "FILE_STORAGE_DELETE_FAILED") from None
    else:
        raise HTTPException(503, "UNKNOWN_STORAGE_BACKEND")
