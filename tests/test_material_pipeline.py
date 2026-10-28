"""No-network regressions for chunking and Gemini citation validation."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from components.chunking import chunk_page, normalize_extraction
from agent.gemini import generate_answer


class ChunkingTests(unittest.TestCase):
    def test_preserves_thai_and_math(self):
        source = "นิยามฟังก์ชัน\n\nf(x) = x² + 1\n\n" + "เสียงและความถี่ " * 160
        result = chunk_page(source, max_chars=400, overlap=40)
        self.assertGreater(len(result), 1)
        self.assertTrue(all(0 < len(x) <= 400 for x in result))
        self.assertIn("f(x) = x² + 1", "\n".join(result))
        self.assertIn("นิยามฟังก์ชัน", result[0])

    def test_empty_and_invalid_config(self):
        self.assertEqual(chunk_page(" \n \n "), [])
        self.assertEqual(normalize_extraction("ฟั\u200bงก์ชัน"), "ฟังก์ชัน")
        with self.assertRaises(ValueError):
            chunk_page("abc", 100, 100)


class GeminiValidationTests(unittest.TestCase):
    def setUp(self):
        self.chunk = {"chunk_id": "source-1", "version_id": "version-1",
            "document_id": "document-1", "text": "ฟังก์ชันเป็นความสัมพันธ์"}

    def _run(self, texts):
        response = MagicMock()
        response.__enter__.return_value.models.generate_content.side_effect = [
            SimpleNamespace(text=value, usage_metadata=None) for value in texts
        ]
        with patch("agent.gemini.AI_ENABLED", True), patch("agent.gemini.LLM_API_KEY", "dummy"), \
             patch("agent.gemini.genai.Client", return_value=response):
            return generate_answer("ฟังก์ชันคืออะไร", [self.chunk])

    def test_repair_invalid_json(self):
        valid = {"intent": "tutor", "answer": "นิยามของฟังก์ชัน", "citations": ["source-1"],
            "next_action": "practice", "needs_clarification": False, "uncertainty_reason": None}
        answer = self._run(["not JSON", json.dumps(valid)])
        self.assertEqual([c["chunk_id"] for c in answer["citations"]], ["source-1"])

    def test_reject_invalid_citation_without_claiming_source(self):
        invalid = {"intent": "tutor", "answer": "คำตอบที่ไม่มีหลักฐาน", "citations": ["invented"],
            "next_action": "none", "needs_clarification": False, "uncertainty_reason": None}
        answer = self._run([json.dumps(invalid), json.dumps(invalid)])
        self.assertEqual(answer["citations"], [])
        self.assertEqual(answer["generation_status"], "INVALID_CITATION")
        self.assertNotIn("คำตอบที่ไม่มีหลักฐาน", answer["answer"])


if __name__ == "__main__":
    unittest.main()
