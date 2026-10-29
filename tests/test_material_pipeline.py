"""Offline regressions using the real OpenAI SDK over a simulated HTTP transport."""
import json
import unittest
from unittest.mock import patch

import httpx
from openai import OpenAI, RateLimitError

from agent import llm
from components import embeddings
from components.chunking import chunk_page, normalize_extraction


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


class OpenAITutorTests(unittest.TestCase):
    def setUp(self):
        settings = patch.multiple(llm, AI_ENABLED=True, LLM_API_KEY="test-only",
            LLM_MODEL="gpt-5.4-mini", LLM_MAX_OUTPUT_TOKENS=4096)
        settings.start()
        self.addCleanup(settings.stop)
        self.chunk = {"chunk_id": "source-1", "version_id": "version-1",
            "document_id": "document-1", "text": "ฟังก์ชันเป็นความสัมพันธ์",
            "page_no": 3, "page_start": 3, "page_end": 4, "topic": "ฟังก์ชัน"}
        self.valid = {"intent": "tutor", "answer": "นิยามของฟังก์ชัน", "citations": ["source-1"],
            "next_action": "practice", "needs_clarification": False, "uncertainty_reason": None}
        self.requests = []

    def run_answers(self, answers, *, status="completed", refusal=False, empty=False, http_status=200):
        pending = iter(answers)

        def respond(request):
            self.requests.append(json.loads(request.content))
            self.assertEqual(request.url.path, "/v1/responses")
            if http_status != 200:
                return httpx.Response(http_status, json={"error": {"message": "test error", "type": "rate_limit_error"}})
            value = next(pending)
            content = [{"type": "refusal", "refusal": "private provider reason"}] if refusal else [
                {"type": "output_text", "text": value if isinstance(value, str) else json.dumps(value), "annotations": []}]
            return httpx.Response(200, json={"id": "resp_test", "object": "response", "created_at": 1,
                "status": status, "model": "gpt-5.4-mini-test-snapshot",
                "output": [] if empty else [{"id": "msg_test", "type": "message", "role": "assistant",
                    "status": status, "content": content}],
                "usage": {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}})

        def client(**kwargs):
            self.assertEqual(kwargs["max_retries"], 0)
            self.assertEqual(kwargs["timeout"], 30.0)
            return OpenAI(**kwargs, base_url="https://api.openai.com/v1",
                http_client=httpx.Client(transport=httpx.MockTransport(respond)))

        with patch.object(llm, "OpenAI", side_effect=client):
            return llm.generate_answer("ฟังก์ชันคืออะไร", [self.chunk],
                [{"role": "user", "text": "ทบทวนบทเรียน"}], {"title": "คณิตศาสตร์"})

    def test_request_schema_citations_and_page_spans(self):
        result = self.run_answers([{**self.valid, "citations": ["source-1", "source-1"]}])
        self.assertEqual(result["citations"], [self.chunk])
        self.assertEqual(result["model"], "gpt-5.4-mini-test-snapshot")
        self.assertEqual(result["usage"], {"input_tokens": 100, "output_tokens": 20})
        body = self.requests[0]
        self.assertEqual(body["model"], "gpt-5.4-mini")
        self.assertEqual(body["max_output_tokens"], 4096)
        self.assertFalse(body["store"])
        self.assertNotIn("temperature", body)
        self.assertTrue(body["text"]["format"]["strict"])
        self.assertEqual(set(body["text"]["format"]["schema"]["required"]), set(self.valid))
        payload = json.loads(body["input"])
        self.assertEqual(payload["untrusted_course_material"], [self.chunk])
        self.assertEqual(payload["course_context"], {"title": "คณิตศาสตร์"})
        self.assertIn("page_end", body["instructions"])

    def test_repair_invalid_json(self):
        result = self.run_answers(["not JSON", self.valid])
        self.assertEqual(result["citations"], [self.chunk])
        self.assertEqual(len(self.requests), 2)
        self.assertIn("format_correction", json.loads(self.requests[1]["input"]))

    def test_repair_invalid_citation_and_sum_usage(self):
        result = self.run_answers([{**self.valid, "citations": ["invented"]}, self.valid])
        self.assertEqual(result["citations"], [self.chunk])
        self.assertEqual(result["usage"], {"input_tokens": 200, "output_tokens": 40})

    def test_reject_invalid_or_missing_citations_after_one_repair(self):
        for citations in (["invented"], []):
            with self.subTest(citations=citations):
                invalid = {**self.valid, "answer": "คำตอบที่ไม่มีหลักฐาน", "citations": citations}
                result = self.run_answers([invalid, invalid])
                self.assertEqual(result["citations"], [])
                self.assertEqual(result["generation_status"], "INVALID_CITATION")
                self.assertNotIn(invalid["answer"], result["answer"])

    def test_invalid_schema_has_safe_fallback(self):
        result = self.run_answers([{}, {}])
        self.assertEqual(result["generation_status"], "MODEL_RESPONSE_SCHEMA_INVALID")
        self.assertEqual(result["citations"], [])

    def test_refusal_is_not_repaired(self):
        result = self.run_answers([{}], refusal=True)
        self.assertEqual(result["generation_status"], "MODEL_REFUSAL")
        self.assertEqual(result["citations"], [])
        self.assertNotIn("private provider reason", result["answer"])
        self.assertEqual(len(self.requests), 1)

    def test_incomplete_and_empty_output_are_not_shown(self):
        result = self.run_answers([{}], status="incomplete", empty=True)
        self.assertEqual(result["generation_status"], "INCOMPLETE_LLM_RESPONSE")
        result = self.run_answers([{}, {}], empty=True)
        self.assertEqual(result["generation_status"], "MODEL_RESPONSE_SCHEMA_INVALID")

    def test_rate_limit_uses_worker_retry_not_sdk_retry(self):
        with self.assertRaises(RateLimitError):
            self.run_answers([], http_status=429)
        self.assertEqual(len(self.requests), 1)

    def test_disabled_missing_key_no_sources_and_missing_model_make_no_request(self):
        with patch.object(llm, "OpenAI") as client:
            self.assertIsNone(llm.generate_answer("question", [])["model"])
            with patch.object(llm, "AI_ENABLED", False):
                self.assertIsNone(llm.generate_answer("question", [self.chunk])["model"])
            with patch.object(llm, "LLM_API_KEY", ""):
                self.assertIsNone(llm.generate_answer("question", [self.chunk])["model"])
            with patch.object(llm, "LLM_MODEL", ""):
                with self.assertRaisesRegex(ValueError, "LLM_MODEL_REQUIRED"):
                    llm.generate_answer("question", [self.chunk])
            client.assert_not_called()


class OpenAIEmbeddingTests(unittest.TestCase):
    def setUp(self):
        settings = patch.multiple(embeddings, EMBEDDINGS_ENABLED=True, LLM_API_KEY="test-only",
            EMBEDDING_MODEL="text-embedding-3-small")
        settings.start()
        self.addCleanup(settings.stop)
        self.requests = []

    def run_vectors(self, items, texts=None, http_status=200):
        def respond(request):
            self.requests.append(json.loads(request.content))
            self.assertEqual(request.url.path, "/v1/embeddings")
            return httpx.Response(http_status, json={"object": "list", "data": items,
                "model": "text-embedding-3-small", "usage": {"prompt_tokens": 4, "total_tokens": 4}})

        def client(**kwargs):
            self.assertEqual(kwargs["timeout"], 15.0)
            self.assertEqual(kwargs["max_retries"], 0)
            return OpenAI(**kwargs, base_url="https://api.openai.com/v1",
                http_client=httpx.Client(transport=httpx.MockTransport(respond)))

        with patch.object(embeddings, "OpenAI", side_effect=client):
            return embeddings.embed_document_batch(texts if texts is not None else ["แรง", "มวล"])

    def item(self, index, values):
        return {"object": "embedding", "index": index, "embedding": values}

    def test_768_dimensions_normalization_and_response_order(self):
        vectors = self.run_vectors([self.item(1, [1.0] * 768), self.item(0, [2.0] + [0.0] * 767)])
        self.assertEqual(vectors[0], [1.0] + [0.0] * 767)
        self.assertAlmostEqual(sum(x*x for x in vectors[1]), 1.0)
        body = self.requests[0]
        self.assertEqual(body["dimensions"], 768)
        self.assertEqual(body["model"], "text-embedding-3-small")
        self.assertEqual(body["input"], ["แรง", "มวล"])
        self.assertEqual(body["encoding_format"], "float")
        self.assertNotIn("task_type", body)

    def test_bad_dimension_empty_zero_and_duplicate_indices_rejected(self):
        cases = [([self.item(0, [1.0])], "EMBEDDING_DIMENSION_MISMATCH"),
            ([], "EMBEDDING_COUNT_MISMATCH"),
            ([self.item(0, [0.0] * 768)], "INVALID_EMBEDDING"),
            ([self.item(1, [1.0] * 768)], "EMBEDDING_COUNT_MISMATCH")]
        for items, code in cases:
            with self.subTest(code=code), self.assertRaisesRegex(ValueError, code):
                self.run_vectors(items, texts=["แรง"])

    def test_no_request_when_disabled_missing_key_or_empty(self):
        with patch.object(embeddings, "OpenAI") as client:
            self.assertEqual(embeddings.embed_document_batch([]), [])
            with patch.object(embeddings, "EMBEDDINGS_ENABLED", False):
                self.assertIsNone(embeddings.embed_query("แรง"))
            with patch.object(embeddings, "LLM_API_KEY", ""):
                self.assertEqual(embeddings.embed_document_batch(["แรง"]), [])
            client.assert_not_called()

    def test_query_and_documents_share_the_embedding_space(self):
        with patch.object(embeddings, "embed_texts", return_value=[[1.0] * 768]) as embed:
            self.assertEqual(len(embeddings.embed_query("แรง")), 768)
            embed.assert_called_once_with(["แรง"])


if __name__ == "__main__":
    unittest.main()
