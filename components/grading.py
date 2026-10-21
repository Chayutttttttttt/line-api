"""Bounded, deterministic grading. Open responses require an authorized teacher."""
from decimal import Decimal, InvalidOperation, localcontext
import re
import unicodedata
from typing import Literal

from fastapi import HTTPException

AnswerType = Literal["integer_set", "boolean", "multiple_choice", "numeric", "short_text", "manual"]


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


def number(value) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError("INVALID_NUMBER")
    text = str(value).strip().replace("−", "-")
    if not re.fullmatch(r"[+-]?(?:[0-9]{1,30}(?:\.[0-9]{0,30})?|\.[0-9]{1,30})(?:[eE][+-]?[0-9]{1,2})?", text):
        raise ValueError("INVALID_NUMBER")
    result = Decimal(text)
    if not result.is_finite() or abs(result) > Decimal("1e50"):
        raise ValueError("INVALID_NUMBER")
    return result


def normalized(value: str, case_sensitive: bool) -> str:
    text = " ".join(unicodedata.normalize("NFC", value).split())
    return text if case_sensitive else text.casefold()


def grade(answer_type: str, spec: dict, answer: str) -> bool | None:
    if not answer.strip():
        raise HTTPException(400, "ANSWER_REQUIRED")
    if answer_type == "integer_set":
        return integer_set(answer) == set(spec["expected"])
    if answer_type == "boolean":
        values = {"true": True, "false": False, "ใช่": True, "ไม่ใช่": False,
            "จริง": True, "เท็จ": False, "ถูก": True, "ผิด": False,
            "เป็นฟังก์ชัน": True, "ไม่เป็นฟังก์ชัน": False}
        if answer.strip().lower() not in values:
            raise HTTPException(400, "UNSUPPORTED_ANSWER: ตอบ จริง หรือ เท็จ")
        return values[answer.strip().lower()] is spec["expected"]
    if answer_type == "multiple_choice":
        if answer not in {o["id"] for o in spec["options"]}:
            raise HTTPException(400, "UNKNOWN_CHOICE")
        return answer == spec["expected"]
    if answer_type == "numeric":
        try:
            with localcontext() as context:
                context.prec = 256
                return abs(number(answer) - number(spec["expected"])) <= number(spec.get("tolerance", 0))
        except (ValueError, InvalidOperation):
            raise HTTPException(400, "UNSUPPORTED_ANSWER: กรอกตัวเลขในหน่วยที่โจทย์กำหนด") from None
    if answer_type == "short_text":
        case_sensitive = spec.get("case_sensitive", False)
        return normalized(answer, case_sensitive) in {normalized(x, case_sensitive) for x in spec["accepted"]}
    if answer_type == "manual":
        return None
    raise HTTPException(400, "UNSUPPORTED_ANSWER")


def validate_spec(answer_type: str, spec: dict):
    expected = spec.get("expected")
    valid = False
    if answer_type == "integer_set" and isinstance(expected, list) and len(expected) <= 100:
        valid = all(type(x) is int and abs(x) < 10**9 for x in expected)
    elif answer_type == "boolean":
        valid = type(expected) is bool
    elif answer_type == "multiple_choice":
        options = spec.get("options")
        if isinstance(options, list) and 2 <= len(options) <= 8 and all(isinstance(o, dict) for o in options):
            ids = [o.get("id") for o in options]
            valid = (all(isinstance(i, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,20}", i) for i in ids)
                and len(set(ids)) == len(ids) and expected in ids
                and all(isinstance(o.get("text"), str) and 0 < len(o["text"].strip()) <= 500 for o in options))
    elif answer_type == "numeric":
        try:
            number(expected)
            valid = number(spec.get("tolerance", 0)) >= 0 and isinstance(spec.get("unit", ""), str) and len(spec.get("unit", "")) <= 64
        except (ValueError, InvalidOperation):
            pass
    elif answer_type == "short_text":
        accepted = spec.get("accepted")
        valid = (isinstance(accepted, list) and 1 <= len(accepted) <= 30
            and all(isinstance(x, str) and 0 < len(x.strip()) <= 500 for x in accepted)
            and type(spec.get("case_sensitive", False)) is bool)
    elif answer_type == "manual":
        valid = isinstance(spec.get("criteria"), str) and 0 < len(spec["criteria"].strip()) <= 4000
    if not valid:
        raise HTTPException(400, "INVALID_GRADING_SPEC")


def student_answer_config(answer_type: str, spec: dict) -> dict:
    # Deliberately allowlist display fields; never expose expected/accepted answers.
    if answer_type == "multiple_choice":
        return {"options": [{"id": o["id"], "text": o["text"]} for o in spec["options"]]}
    if answer_type == "numeric":
        return {"unit": spec.get("unit", "")}
    if answer_type == "manual":
        return {"criteria": spec["criteria"]}
    return {}
