"""Offline PDF-to-semantic-chunks coverage with the real OpenAI SDK."""
import base64
from io import BytesIO
import json
import unittest
from unittest.mock import patch

import httpx
from openai import OpenAI, RateLimitError
from pypdf import PdfReader, PdfWriter

from components import pdf_ai
from components.semantic_chunking import build_semantic_chunks


class OpenAIPdfReaderTests(unittest.TestCase):
    def setUp(self):
        settings = patch.multiple(pdf_ai, LLM_API_KEY="test-only", PDF_READER_MODEL="gpt-5.4-mini",
            PDF_AI_MAX_PAGES=10, PDF_MAX_OUTPUT_TOKENS=16384)
        settings.start()
        self.addCleanup(settings.stop)
        self.requests = []
        self.events = []
        self.valid = {"sections": [{"topic": "กฎข้อที่ 2 ของนิวตัน",
            "text": "ฟิสิกส์\n\nF = ma", "keywords": ["ฟิสิกส์", "แรง", "แรง", "มวล"]}], "warnings": []}

    def pdf(self, count=1, encrypted=False):
        writer = PdfWriter()
        for i in range(count):
            writer.add_blank_page(width=595 + i, height=842)
        if encrypted:
            writer.encrypt("test-password")
        out = BytesIO()
        writer.write(out)
        return out.getvalue()

    def read(self, answers, *, status="completed", refusal=False, empty=False, http_status=200):
        pending = iter(answers)

        def respond(request):
            self.requests.append(json.loads(request.content))
            self.assertEqual(request.url.path, "/v1/responses")
            if http_status != 200:
                return httpx.Response(http_status, json={"error": {"message": "rate limit", "type": "rate_limit_error"}})
            value = next(pending)
            content = [{"type": "refusal", "refusal": "not allowed"}] if refusal else [
                {"type": "output_text", "text": value if isinstance(value, str) else json.dumps(value), "annotations": []}]
            return httpx.Response(200, json={"id": "resp_pdf", "object": "response", "created_at": 1,
                "status": status, "model": "gpt-5.4-mini", "output": [] if empty else [
                    {"id": "msg_pdf", "type": "message", "role": "assistant", "status": status, "content": content}]})

        def client(**kwargs):
            self.assertEqual(kwargs["timeout"], 60.0)
            self.assertEqual(kwargs["max_retries"], 0)
            return OpenAI(**kwargs, base_url="https://api.openai.com/v1",
                http_client=httpx.Client(transport=httpx.MockTransport(respond)))

        with patch.object(pdf_ai, "OpenAI", side_effect=client):
            return pdf_ai.read_pdf_with_openai(self.pdf(len(answers)),
                on_page=lambda n, total: self.events.append((n, total)))

    def test_extracts_pdf_page_sections_keywords_and_strict_schema(self):
        result = self.read([self.valid])
        self.assertEqual(result, [(1, "ฟิสิกส์\n\nF = ma", ["ฟิสิกส์", "แรง", "มวล"], None,
            [{"topic": "กฎข้อที่ 2 ของนิวตัน", "text": "ฟิสิกส์\n\nF = ma", "keywords": ["ฟิสิกส์", "แรง", "มวล"]}])])
        self.assertEqual(self.events, [(1, 1)])
        body = self.requests[0]
        self.assertEqual(body["model"], "gpt-5.4-mini")
        self.assertFalse(body["store"])
        self.assertNotIn("temperature", body)
        self.assertEqual(body["max_output_tokens"], 16384)
        self.assertTrue(body["text"]["format"]["strict"])
        content = body["input"][0]["content"][0]
        self.assertEqual(content["type"], "input_file")
        self.assertEqual(content["filename"], "page-1.pdf")
        header, encoded = content["file_data"].split(",", 1)
        self.assertEqual(header, "data:application/pdf;base64")
        self.assertEqual(len(PdfReader(BytesIO(base64.b64decode(encoded))).pages), 1)

    def test_two_pages_keep_topic_context_merge_and_page_spans(self):
        second = {"sections": [{"topic": "กฎข้อที่ 2 ของนิวตัน", "text": "a = F/m", "keywords": ["ความเร่ง"]}], "warnings": []}
        result = self.read([self.valid, second])
        self.assertEqual(self.events, [(1, 2), (2, 2)])
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(json.loads(self.requests[1]["input"][0]["content"][1]["text"]),
            {"previous_topic": "กฎข้อที่ 2 ของนิวตัน"})
        self.assertNotIn("กฎข้อที่ 2 ของนิวตัน", self.requests[1]["instructions"])
        for i, request in enumerate(self.requests):
            data = base64.b64decode(request["input"][0]["content"][0]["file_data"].split(",", 1)[1])
            pages = PdfReader(BytesIO(data)).pages
            self.assertEqual(len(pages), 1)
            self.assertEqual(float(pages[0].mediabox.width), 595 + i)
        chunks = build_semantic_chunks(result)
        self.assertEqual(len(chunks), 1)
        self.assertEqual((chunks[0]["page_no"], chunks[0]["page_end"]), (1, 2))
        self.assertIn("F = ma", chunks[0]["text"])
        self.assertIn("a = F/m", chunks[0]["text"])

    def test_configuration_and_invalid_pdf_fail_before_network(self):
        with patch.object(pdf_ai, "OpenAI") as client:
            with patch.object(pdf_ai, "LLM_API_KEY", ""), self.assertRaisesRegex(ValueError, "PDF_AI_KEY_NOT_CONFIGURED"):
                pdf_ai.read_pdf_with_openai(self.pdf())
            with patch.object(pdf_ai, "PDF_READER_MODEL", ""), self.assertRaisesRegex(ValueError, "PDF_AI_MODEL_NOT_CONFIGURED"):
                pdf_ai.read_pdf_with_openai(self.pdf())
            with self.assertRaisesRegex(ValueError, "INVALID_PDF"):
                pdf_ai.read_pdf_with_openai(b"not a PDF")
            for data in (self.pdf(11), self.pdf(encrypted=True)):
                with self.assertRaisesRegex(ValueError, "ENCRYPTED_OR_TOO_MANY_PAGES"):
                    pdf_ai.read_pdf_with_openai(data)
            client.assert_not_called()

    def test_malformed_schema_empty_topic_and_empty_output_are_rejected(self):
        cases = ["{bad json", {}, {"sections": [{"topic": " ", "text": "เนื้อหา", "keywords": []}], "warnings": []}]
        for value in cases:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "PDF_AI_RESPONSE_INVALID"):
                self.read([value])
        with self.assertRaisesRegex(ValueError, "PDF_AI_RESPONSE_INVALID"):
            self.read([{}], empty=True)

    def test_incomplete_and_refusal_are_not_accepted_as_source(self):
        with self.assertRaisesRegex(ValueError, "PDF_AI_RESPONSE_INCOMPLETE"):
            self.read([self.valid], status="incomplete")
        with self.assertRaisesRegex(ValueError, "PDF_AI_REFUSAL"):
            self.read([{}], refusal=True)

    def test_later_page_failure_does_not_return_partial_document(self):
        with self.assertRaisesRegex(ValueError, "PDF_AI_RESPONSE_INVALID"):
            self.read([self.valid, "bad json"])
        self.assertEqual(len(self.requests), 2)

    def test_blank_pages_warnings_and_size_limits(self):
        blank = {"sections": [], "warnings": ["อ่านไม่ชัด"]}
        with self.assertRaisesRegex(ValueError, "PDF_AI_NO_SEARCHABLE_TEXT"):
            self.read([blank])
        pages = self.read([blank, self.valid])
        self.assertEqual(pages[0][3], "อ่านไม่ชัด")
        self.assertEqual(build_semantic_chunks(pages)[0]["page_no"], 2)
        oversized = {"sections": [{"topic": "ยาว", "text": "ก" * 24001, "keywords": []}], "warnings": []}
        with self.assertRaisesRegex(ValueError, "PDF_PAGE_TOO_LONG"):
            self.read([oversized])

    def test_rate_limit_is_left_for_worker_and_not_retried_by_sdk(self):
        with self.assertRaises(RateLimitError):
            self.read([{}], http_status=429)
        self.assertEqual(len(self.requests), 1)

    def test_normalizes_duplicate_keywords(self):
        self.assertEqual(pdf_ai._keywords(["แรง", " แรง ", "มวล", "x", ""]), ["แรง", "มวล"])


if __name__ == "__main__":
    unittest.main()
