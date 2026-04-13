from pathlib import Path
import tempfile

from backend.object_storage import MinioArchiveService


class _FakeMinioClient:
    def __init__(self):
        self.uploads = []

    def bucket_exists(self, bucket):
        return True

    def make_bucket(self, bucket):
        raise AssertionError("bucket already exists")

    def fput_object(self, bucket, object_key, file_path):
        path = Path(file_path)
        assert path.exists()
        self.uploads.append((bucket, object_key, path.name))


def test_archive_directory_cleans_up_temporary_zip(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "result.txt").write_text("done\n", encoding="utf-8")

    fake_client = _FakeMinioClient()
    service = MinioArchiveService(
        enabled=True,
        endpoint="minio.local",
        access_key="key",
        secret_key="secret",
        bucket="task-artifacts",
        client_factory=lambda **kwargs: fake_client,
    )

    artifacts = service.archive_directory("task_demo", source_dir)

    assert fake_client.uploads == [("task-artifacts", artifacts[0]["minio_object_key"], artifacts[0]["display_name"])]
    temp_archive = Path(tempfile.gettempdir()) / artifacts[0]["display_name"]
    assert not temp_archive.exists()
