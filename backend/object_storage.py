"""
Object storage archive helpers (MinIO / S3-compatible).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile
import zipfile


@dataclass
class MinioArchiveService:
    enabled: bool
    endpoint: str
    access_key: str
    secret_key: str
    bucket: str
    secure: bool = False
    client_factory: object | None = None

    def _build_client(self):
        if self.client_factory:
            return self.client_factory(
                endpoint=self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
            )
        from minio import Minio
        return Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure,
        )

    def archive_directory(self, task_id: str, source_dir: Path) -> list[dict]:
        if not self.enabled:
            return []
        source_dir = Path(source_dir)
        if not source_dir.exists():
            return []

        client = self._build_client()
        if not client.bucket_exists(self.bucket):
            client.make_bucket(self.bucket)

        with tempfile.NamedTemporaryFile(prefix=f"{task_id}-", suffix=".zip", delete=False) as tmp_file:
            archive_path = Path(tmp_file.name)
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path in sorted(source_dir.rglob("*")):
                if not file_path.is_file():
                    continue
                archive.write(file_path, file_path.relative_to(source_dir).as_posix())

        object_key = f"tasks/{task_id}/{archive_path.name}"
        client.fput_object(self.bucket, object_key, str(archive_path))
        return [
            {
                "artifact_kind": "minio_archive",
                "display_name": archive_path.name,
                "minio_bucket": self.bucket,
                "minio_object_key": object_key,
                "size_bytes": archive_path.stat().st_size,
            }
        ]
