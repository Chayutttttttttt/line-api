"""Offline semantic chunk boundary and source provenance tests."""
import unittest

from components.semantic_chunking import build_semantic_chunks


def pdf_page(number, *sections):
    items = [{"topic": topic, "text": text, "keywords": words}
             for topic, text, words in sections]
    content = "\n\n".join(section["text"] for section in items)
    terms = [word for section in items for word in section["keywords"]]
    return (number, content, terms, None, items)


class SemanticChunkingTests(unittest.TestCase):
    def test_merges_contiguous_pages_with_same_topic(self):
        pages = [
            pdf_page(3, ("กฎข้อที่ 2 ของนิวตัน", "แรงลัพธ์ F = ma", ["แรง", "มวล"])),
            pdf_page(4, ("กฎข้อที่ 2 ของนิวตัน", "ความเร่ง a = F/m", ["ความเร่ง", "มวล"])),
        ]
        chunks = build_semantic_chunks(pages, max_chars=300)
        self.assertEqual(len(chunks), 1)
        self.assertEqual((chunks[0]["page_no"], chunks[0]["page_end"]), (3, 4))
        self.assertEqual(chunks[0]["topic"], "กฎข้อที่ 2 ของนิวตัน")
        self.assertEqual(chunks[0]["text"], "แรงลัพธ์ F = ma\n\nความเร่ง a = F/m")
        self.assertEqual(chunks[0]["keywords"], ["แรง", "มวล", "ความเร่ง"])

    def test_two_topics_on_one_page_never_merge(self):
        chunks = build_semantic_chunks([
            pdf_page(1, ("แรง", "สูตรแรง F = ma", ["แรง"]),
                ("พลังงาน", "พลังงาน E = mc²", ["พลังงาน"]))
        ], max_chars=300)
        self.assertEqual(len(chunks), 2)
        self.assertEqual([c["topic"] for c in chunks], ["แรง", "พลังงาน"])
        self.assertEqual([c["page_no"] for c in chunks], [1, 1])

    def test_different_topics_on_adjacent_pages_do_not_merge(self):
        pages = [pdf_page(1, ("กฎข้อที่ 1", "ข้อความแรก", ["แรง"])),
                 pdf_page(2, ("กฎข้อที่ 2", "ข้อความถัดไป", ["มวล"]))]
        self.assertEqual(len(build_semantic_chunks(pages)), 2)

    def test_blank_and_noncontiguous_pages_do_not_collapse(self):
        pages = [pdf_page(1, ("ความเร่ง", "a = F/m", ["ความเร่ง"])),
                 (2, "", [], "หน้าว่าง", []),
                 pdf_page(3, ("ความเร่ง", "คำนวณความเร่ง", ["ความเร่ง"]))]
        chunks = build_semantic_chunks(pages)
        self.assertEqual(len(chunks), 2)
        self.assertEqual([c["page_end"] for c in chunks], [1, 3])

    def test_long_semantic_section_has_size_safety_limit(self):
        text = ("การทดลองเพื่อสังเกตความสัมพันธ์ระหว่างแรงและมวล\n\n" * 20).strip()
        chunks = build_semantic_chunks([pdf_page(7, ("การทดลอง", text, ["แรง"]))],
                                       max_chars=300)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c["text"]) <= 300 for c in chunks))
        self.assertTrue(all(c["page_no"] == 7 and c["page_end"] == 7 for c in chunks))
        self.assertTrue(all(c["topic"] == "การทดลอง" for c in chunks))

    def test_legacy_unlabeled_pages_keep_individual_provenance(self):
        chunks = build_semantic_chunks([(1, "ความรู้", [], None), (2, "ความรู้", [], None)])
        self.assertEqual(len(chunks), 2)
        self.assertEqual([c["page_end"] for c in chunks], [1, 2])

    def test_oversize_text_with_small_subsection_breaks_and_keeps_order(self):
        pages = [pdf_page(1, ("กฎแรง", "แรงเริ่มต้น", ["แรง"])),
                 pdf_page(2, ("กฎแรง", "แรงสิ้นสุด", ["แรง"]))]
        chunks = build_semantic_chunks(pages, max_chars=100)
        self.assertEqual(len(chunks), 1)
        self.assertIn("แรงเริ่มต้น\n\nแรงสิ้นสุด", chunks[0]["text"])


if __name__ == "__main__":
    unittest.main()
