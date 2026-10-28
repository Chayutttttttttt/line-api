"""Offline regression tests for teacher document deletion and storage cleanup."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException

from components.documents import RevisionRequest, delete_document_version
from components.storage import delete_file


def result(*, first=None, all_items=None, count=0):
    query_result = MagicMock()
    query_result.first.return_value = first
    query_result.all.return_value = all_items or []
    query_result.rowcount = count
    return query_result


class DocumentDeletionTests(unittest.TestCase):
    def setUp(self):
        self.version_id = uuid4()
        self.document = SimpleNamespace(id=uuid4(), course_id=uuid4())
        self.version = SimpleNamespace(id=self.version_id, document_id=self.document.id,
            status="failed", revision=3, storage_key="school/course/test.pdf")
        self.user = SimpleNamespace(id=uuid4())
        self.db = MagicMock()

    def delete(self):
        return delete_document_version(self.version_id, RevisionRequest(expected_revision=3),
            user=self.user, db=self.db)

    def test_failed_file_deletes_storage_chunks_reviews_jobs_and_empty_document(self):
        self.db.exec.side_effect = [
            result(all_items=[]), result(), result(),    # initial preflight
            result(), result(),                          # reference recheck
            result(count=4), result(count=2), result(count=1),  # SQL delete counts
            result(),                                     # no remaining versions
        ]
        with patch("components.documents.version_access", return_value=(self.document, self.version)), \
             patch("components.documents.delete_file") as storage:
            answer = self.delete()
        self.assertTrue(answer["deleted"])
        self.assertEqual((answer["chunks_deleted"], answer["reviews_deleted"], answer["jobs_deleted"]), (4, 2, 1))
        self.assertTrue(answer["document_deleted"])
        self.assertEqual(self.version.status, "deleting")
        self.assertEqual(self.version.revision, 4)
        self.assertEqual(self.db.commit.call_count, 2)
        self.db.delete.assert_any_call(self.version)
        self.db.delete.assert_any_call(self.document)
        storage.assert_called_once_with(self.version.storage_key)

    def test_published_file_must_be_withdrawn_before_delete(self):
        self.version.status = "published"
        with patch("components.documents.version_access", return_value=(self.document, self.version)), \
             patch("components.documents.delete_file") as storage:
            with self.assertRaises(HTTPException) as raised:
                self.delete()
        self.assertEqual(raised.exception.detail, "WITHDRAW_PUBLISHED_DOCUMENT_FIRST")
        storage.assert_not_called()

    def test_active_job_blocks_delete(self):
        self.db.exec.return_value = result(all_items=[SimpleNamespace(state="running")])
        with patch("components.documents.version_access", return_value=(self.document, self.version)), \
             patch("components.documents.delete_file") as storage:
            with self.assertRaises(HTTPException) as raised:
                self.delete()
        self.assertEqual(raised.exception.detail, "DOCUMENT_JOB_STILL_RUNNING")
        self.db.commit.assert_not_called()
        storage.assert_not_called()

    def test_storage_failure_keeps_retry_marker_and_metadata(self):
        self.db.exec.side_effect = [result(all_items=[]), result(), result()]
        with patch("components.documents.version_access", return_value=(self.document, self.version)), \
             patch("components.documents.delete_file", side_effect=HTTPException(503, "FILE_STORAGE_DELETE_FAILED")):
            with self.assertRaises(HTTPException) as raised:
                self.delete()
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(self.version.status, "deleting")
        self.assertEqual(self.db.commit.call_count, 1)
        self.db.delete.assert_not_called()

    def test_delete_retry_ignores_old_revision_and_completes(self):
        self.version.status = "deleting"
        self.version.revision = 4
        self.db.exec.side_effect = [
            result(), result(), result(count=0), result(count=0), result(count=0), result(first=self.version_id)
        ]
        with patch("components.documents.version_access", return_value=(self.document, self.version)), \
             patch("components.documents.delete_file") as storage:
            answer = self.delete()
        self.assertTrue(answer["deleted"])
        self.assertFalse(answer["document_deleted"])
        self.assertEqual(self.db.commit.call_count, 1)
        storage.assert_called_once()


class StorageDeletionTests(unittest.TestCase):
    def test_deletes_one_s3_object_not_bucket(self):
        s3 = MagicMock()
        with patch("components.storage.STORAGE_BACKEND", "s3"), \
             patch("components.storage.s3_client", return_value=s3):
            delete_file("school/course/a.pdf")
        s3.delete_object.assert_called_once()
        self.assertEqual(s3.delete_object.call_args.kwargs["Key"], "school/course/a.pdf")
        s3.delete_bucket.assert_not_called()

    def test_local_deletion_is_idempotent(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "school" / "course" / "a.pdf"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"test")
            with patch("components.storage.STORAGE_BACKEND", "local"), \
                 patch("components.storage.FILE_STORAGE_ROOT", root):
                delete_file("school/course/a.pdf")
                delete_file("school/course/a.pdf")
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
