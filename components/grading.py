"""Deterministic checking for the teacher-approved finite-relation pilot."""
import re

from fastapi import HTTPException


def integer_set(value: str) -> set[int]:
    text = value.strip().replace("−", "-")
    if text in {"∅", "{}", "{ }"}:
        return set()
    if not text.startswith("{") or not text.endswith("}"):
        raise HTTPException(400, "UNSUPPORTED_ANSWER: ใช้เซตจำนวนเต็ม เช่น {-2, 0, 3}")
    parts = text[1:-1].split(",")
    if len(parts) > 100 or not all(re.fullmatch(r"\s*[+-]?\d{1,9}\s*", p) for p in parts):
        raise HTTPException(400, "UNSUPPORTED_ANSWER")
    return {int(p) for p in parts}


def grade(answer_type: str, spec: dict, answer: str) -> bool:
    if answer_type == "integer_set":
        return integer_set(answer) == {int(x) for x in spec["expected"]}
    if answer_type == "boolean":
        values = {"true": True, "false": False, "ใช่": True, "ไม่ใช่": False,
            "เป็นฟังก์ชัน": True, "ไม่เป็นฟังก์ชัน": False}
        if answer.strip().lower() not in values:
            raise HTTPException(400, "UNSUPPORTED_ANSWER: ตอบ ใช่ หรือ ไม่ใช่")
        return values[answer.strip().lower()] is spec["expected"]
    raise HTTPException(400, "UNSUPPORTED_ANSWER")


def validate_spec(answer_type: str, spec: dict):
    expected = spec.get("expected")
    if answer_type == "integer_set" and isinstance(expected, list) and len(expected) <= 100:
        if all(type(x) is int and abs(x) < 10**9 for x in expected):
            return
    if answer_type == "boolean" and type(expected) is bool:
        return
    raise HTTPException(400, "INVALID_GRADING_SPEC")
