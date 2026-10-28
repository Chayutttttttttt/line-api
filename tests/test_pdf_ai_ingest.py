"""Offline coverage for the Gemini PDF document reader; no network or API cost."""
from io import BytesIO
import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pypdf import PdfWriter
from components.pdf_ai import read_pdf_with_gemini, _keywords


class GeminiPdfReaderTests(unittest.TestCase):
    def pdf(self, count=1):
        writer = PdfWriter()
        for _ in range(count):
            writer.add_blank_page(width=595, height=842)
        out = BytesIO()
        writer.write(out)
        return out.getvalue()

    def test_extracts_pdf_page_and_keywords(self):
        client = MagicMock()
        client.__enter__.return_value.models.generate_content.return_value = SimpleNamespace(
            text=json.dumps({"text": "ฟิสิกส์\n\nF = ma", "keywords": ["ฟิสิกส์", "แรง", "แรง", "มวล"], "warnings": []},
                ensure_ascii=False))
        events = []
        with patch("components.pdf_ai.LLM_API_KEY", "test-only"), \
             patch("components.pdf_ai.PDF_AI_MAX_PAGES", 10), \
             patch("components.pdf_ai.genai.Client", return_value=client):
            result = read_pdf_with_gemini(self.pdf(), on_page=lambda n, total: events.append((n, total)))
        self.assertEqual(result, [(1, "ฟิสิกส์\n\nF = ma", ["ฟิสิกส์", "แรง", "มวล"], None)])
        self.assertEqual(events, [(1, 1)])
        args = client.__enter__.return_value.models.generate_content.call_args
        self.assertEqual(args.kwargs["contents"][0].inline_data.mime_type, "application/pdf")

    def test_requires_key_and_rejects_bad_pdf(self):
        with patch("components.pdf_ai.LLM_API_KEY", None):
            with self.assertRaisesRegex(ValueError, "PDF_AI_KEY_NOT_CONFIGURED"):
                read_pdf_with_gemini(self.pdf())
        with patch("components.pdf_ai.LLM_API_KEY", "test"):
            with self.assertRaisesRegex(ValueError, "INVALID_PDF"):
                read_pdf_with_gemini(b"not a PDF")

    def test_rejects_partial_model_response_without_publishing(self):
        client = MagicMock()
        client.__enter__.return_value.models.generate_content.return_value = SimpleNamespace(text="{bad json")
        with patch("components.pdf_ai.LLM_API_KEY", "test-only"), \
             patch("components.pdf_ai.genai.Client", return_value=client):
            with self.assertRaisesRegex(ValueError, "PDF_AI_RESPONSE_INVALID"):
                read_pdf_with_gemini(self.pdf())

    def test_normalizes_duplicate_keywords(self):
        self.assertEqual(_keywords(["แรง", " แรง ", "มวล", "x", ""]), ["แรง", "มวล"])


if __name__ == "__main__":
    unittest.main()
