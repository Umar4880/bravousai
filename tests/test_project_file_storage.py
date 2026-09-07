import io
import types
import unittest
import uuid

from app.services import object_storage_service as object_storage_module
from app.services.object_storage_service import ObjectStorageService
from app.services.project_file_service import ProjectFileService, sanitize_filename


def make_client_error():
    try:
        return object_storage_module.ClientError({"Error": {"Code": "404"}}, "Head")
    except TypeError:
        return object_storage_module.ClientError()


class FakeS3Client:
    def __init__(self):
        self.buckets = set()
        self.objects = {}
        self.created_buckets = []

    def head_bucket(self, Bucket):
        if Bucket not in self.buckets:
            raise make_client_error()

    def create_bucket(self, Bucket):
        self.buckets.add(Bucket)
        self.created_buckets.append(Bucket)

    def upload_fileobj(self, fileobj, bucket, key, ExtraArgs=None):
        self.objects[(bucket, key)] = {
            "body": fileobj.read(),
            "content_type": (ExtraArgs or {}).get("ContentType"),
        }

    def get_object(self, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            raise make_client_error()
        return {"Body": io.BytesIO(self.objects[(Bucket, Key)]["body"])}

    def delete_object(self, Bucket, Key):
        self.objects.pop((Bucket, Key), None)

    def head_object(self, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            raise make_client_error()


class FakeUploadFile:
    def __init__(self, filename, content_type, content):
        self.filename = filename
        self.content_type = content_type
        self.file = io.BytesIO(content)


class FakeProjectRepository:
    def __init__(self, state):
        self.state = state

    async def create_file_metadata(self, **kwargs):
        if self.state.get("fail_create"):
            raise RuntimeError("db failed")
        record = types.SimpleNamespace(
            id=kwargs["file_id"],
            user_id=kwargs["user_id"],
            project_id=kwargs["project_id"],
            conversation_id=kwargs["conversation_id"],
            original_filename=kwargs["original_filename"],
            safe_filename=kwargs["safe_filename"],
            content_type=kwargs["content_type"],
            size_bytes=kwargs["size_bytes"],
            sha256=kwargs["sha256"],
            storage_bucket=kwargs["storage_bucket"],
            storage_key=kwargs["storage_key"],
            status="uploaded",
            created_at=self.state["now"],
            deleted_at=None,
        )
        self.state["files"][record.id] = record
        return record

    async def get_file_metadata(self, *, file_id, user_id, include_deleted=False):
        record = self.state["files"].get(file_id)
        if record is None or record.user_id != user_id:
            return None
        if not include_deleted and record.status != "uploaded":
            return None
        return record

    async def list_files(self, *, project_id, user_id):
        return [
            record
            for record in self.state["files"].values()
            if record.project_id == project_id and record.user_id == user_id and record.status == "uploaded"
        ]

    async def mark_file_deleted(self, *, file_id, user_id):
        record = await self.get_file_metadata(file_id=file_id, user_id=user_id)
        if record is None:
            return None
        record.status = "deleted"
        record.deleted_at = self.state["now"]
        return record


class FakeUnitOfWork:
    def __init__(self, state):
        self.state = state
        self.projects = FakeProjectRepository(state)
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    async def commit(self):
        self.committed = True


class ProjectFileStorageTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.user_id = uuid.uuid4()
        self.other_user_id = uuid.uuid4()
        self.project_id = uuid.uuid4()
        self.state = {
            "files": {},
            "now": types.SimpleNamespace(isoformat=lambda: "2026-06-14T00:00:00+00:00"),
        }
        self.s3 = FakeS3Client()
        self.storage = ObjectStorageService(client=self.s3)
        self.service = ProjectFileService(
            storage=self.storage,
            uow_factory=lambda: FakeUnitOfWork(self.state),
            bucket="project-files",
            max_upload_bytes=25,
        )

    def test_bucket_creation(self):
        self.storage.ensure_bucket_exists("project-files")
        self.assertIn("project-files", self.s3.created_buckets)

    async def test_successful_upload_stores_object_and_metadata(self):
        record = await self.service.upload_project_file(
            user_id=self.user_id,
            project_id=self.project_id,
            conversation_id=None,
            upload_file=FakeUploadFile("notes.txt", "text/plain", b"hello"),
        )

        self.assertEqual(record.original_filename, "notes.txt")
        self.assertEqual(record.size_bytes, 5)
        self.assertEqual(len(record.sha256), 64)
        self.assertEqual(self.s3.objects[(record.storage_bucket, record.storage_key)]["body"], b"hello")

    async def test_unsafe_filename_sanitized(self):
        record = await self.service.upload_project_file(
            user_id=self.user_id,
            project_id=self.project_id,
            conversation_id=None,
            upload_file=FakeUploadFile("../bad name?.txt", "text/plain", b"x"),
        )

        self.assertEqual(record.safe_filename, "bad_name_.txt")
        self.assertNotIn("..", record.storage_key)

    async def test_disallowed_mime_rejected(self):
        with self.assertRaises(ValueError):
            await self.service.upload_project_file(
                user_id=self.user_id,
                project_id=self.project_id,
                conversation_id=None,
                upload_file=FakeUploadFile("script.js", "application/javascript", b"alert(1)"),
            )

    async def test_oversized_file_rejected(self):
        with self.assertRaises(ValueError):
            await self.service.upload_project_file(
                user_id=self.user_id,
                project_id=self.project_id,
                conversation_id=None,
                upload_file=FakeUploadFile("big.txt", "text/plain", b"x" * 26),
            )

    async def test_duplicate_filename_creates_unique_key(self):
        first = await self.service.upload_project_file(
            user_id=self.user_id,
            project_id=self.project_id,
            conversation_id=None,
            upload_file=FakeUploadFile("same.txt", "text/plain", b"one"),
        )
        second = await self.service.upload_project_file(
            user_id=self.user_id,
            project_id=self.project_id,
            conversation_id=None,
            upload_file=FakeUploadFile("same.txt", "text/plain", b"two"),
        )

        self.assertNotEqual(first.id, second.id)
        self.assertNotEqual(first.storage_key, second.storage_key)

    async def test_metadata_fetch_works(self):
        record = await self.service.upload_project_file(
            user_id=self.user_id,
            project_id=self.project_id,
            conversation_id=None,
            upload_file=FakeUploadFile("notes.md", "text/markdown", b"# hi"),
        )

        fetched = await self.service.get_file_metadata(file_id=record.id, user_id=self.user_id)
        self.assertEqual(fetched.id, record.id)

    async def test_list_project_files_works(self):
        await self.service.upload_project_file(
            user_id=self.user_id,
            project_id=self.project_id,
            conversation_id=None,
            upload_file=FakeUploadFile("a.txt", "text/plain", b"a"),
        )

        files = await self.service.list_project_files(user_id=self.user_id, project_id=self.project_id)
        self.assertEqual(len(files), 1)

    async def test_download_returns_original_bytes(self):
        record = await self.service.upload_project_file(
            user_id=self.user_id,
            project_id=self.project_id,
            conversation_id=None,
            upload_file=FakeUploadFile("image.png", "image/png", b"png-bytes"),
        )

        downloaded = await self.service.download_project_file(file_id=record.id, user_id=self.user_id)
        self.assertEqual(downloaded.content, b"png-bytes")

    async def test_delete_removes_object_and_soft_deletes_metadata(self):
        record = await self.service.upload_project_file(
            user_id=self.user_id,
            project_id=self.project_id,
            conversation_id=None,
            upload_file=FakeUploadFile("delete.txt", "text/plain", b"bye"),
        )

        deleted = await self.service.delete_project_file(file_id=record.id, user_id=self.user_id)
        self.assertEqual(deleted.status, "deleted")
        self.assertNotIn((record.storage_bucket, record.storage_key), self.s3.objects)

    async def test_user_cannot_access_another_users_file(self):
        record = await self.service.upload_project_file(
            user_id=self.user_id,
            project_id=self.project_id,
            conversation_id=None,
            upload_file=FakeUploadFile("private.txt", "text/plain", b"secret"),
        )

        with self.assertRaises(PermissionError):
            await self.service.get_file_metadata(file_id=record.id, user_id=self.other_user_id)

    async def test_cleanup_occurs_if_db_write_fails_after_object_upload(self):
        self.state["fail_create"] = True

        with self.assertRaises(RuntimeError):
            await self.service.upload_project_file(
                user_id=self.user_id,
                project_id=self.project_id,
                conversation_id=None,
                upload_file=FakeUploadFile("cleanup.txt", "text/plain", b"cleanup"),
            )

        self.assertEqual(self.s3.objects, {})


class FilenameTests(unittest.TestCase):
    def test_sanitize_filename_fallback(self):
        self.assertEqual(sanitize_filename("../../"), "uploaded-file")


if __name__ == "__main__":
    unittest.main()
