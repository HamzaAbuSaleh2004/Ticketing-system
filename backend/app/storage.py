"""Where attachment bytes actually live. `LocalStorage` (today's volume) and
`GcsStorage` (Cloud Storage, ADC only — no key files) implement the same
`Storage` protocol, so the router code never knows which one is behind it.

The DB stores a storage *key* (e.g. `"42/3f9a1b_report.pdf"`), never an
absolute path or a public/signed URL: downloads always go back through the
API (`app/routers/attachments.py`), which re-checks role/internal-note
visibility on every request, the same as before this split existed."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Protocol

from app.config import Settings, get_settings


class Storage(Protocol):
    async def save(self, key: str, data: bytes, content_type: str) -> None: ...
    async def open(self, key: str) -> bytes: ...
    async def delete(self, key: str) -> None: ...


class LocalStorage:
    """Today's behaviour, keyed instead of absolute-pathed. `base_dir` is
    resolved once; every key is re-checked to stay inside it, since the key
    ultimately comes from a DB row and a corrupted one shouldn't be able to
    read or write outside the attachments directory."""

    def __init__(self, base_dir: str) -> None:
        self._base = Path(base_dir).resolve()

    def _resolve(self, key: str) -> Path:
        path = (self._base / key).resolve()
        if not path.is_relative_to(self._base):
            raise ValueError(f"storage key escapes the attachments directory: {key!r}")
        return path

    async def save(self, key: str, data: bytes, content_type: str) -> None:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    async def open(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        return path.read_bytes()

    async def delete(self, key: str) -> None:
        self._resolve(key).unlink(missing_ok=True)


class GcsStorage:
    """Cloud Storage backend. Credentials are Application Default Credentials
    (the Cloud Run service account in prod) — never a downloaded key file.
    The `google-cloud-storage` client is sync-only, so every call runs in a
    worker thread rather than blocking the event loop."""

    def __init__(self, bucket_name: str, client=None) -> None:
        if client is None:
            from google.cloud import storage as gcs

            client = gcs.Client()
        self._client = client
        self._bucket = client.bucket(bucket_name)

    def _save_sync(self, key: str, data: bytes, content_type: str) -> None:
        blob = self._bucket.blob(key)
        blob.upload_from_string(data, content_type=content_type)

    def _open_sync(self, key: str) -> bytes:
        from google.cloud.exceptions import NotFound

        blob = self._bucket.blob(key)
        try:
            return blob.download_as_bytes()
        except NotFound as exc:
            raise FileNotFoundError(key) from exc

    def _delete_sync(self, key: str) -> None:
        from google.cloud.exceptions import NotFound

        try:
            self._bucket.blob(key).delete()
        except NotFound:
            pass

    async def save(self, key: str, data: bytes, content_type: str) -> None:
        await asyncio.to_thread(self._save_sync, key, data, content_type)

    async def open(self, key: str) -> bytes:
        return await asyncio.to_thread(self._open_sync, key)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._delete_sync, key)


def build_storage(settings: Settings) -> Storage:
    if settings.ATTACHMENTS_BACKEND == "gcs":
        if not settings.ATTACHMENTS_BUCKET:
            raise RuntimeError("ATTACHMENTS_BUCKET must be set when ATTACHMENTS_BACKEND=gcs")
        return GcsStorage(settings.ATTACHMENTS_BUCKET)
    return LocalStorage(settings.ATTACHMENTS_DIR)


def get_storage() -> Storage:
    """FastAPI dependency. Built fresh per call (cheap for both backends —
    `LocalStorage` is a `Path`, and the GCS client is a lightweight handle
    with no network call at construction time), so a test overriding
    `ATTACHMENTS_BACKEND`/`ATTACHMENTS_BUCKET` on the live settings singleton
    takes effect on the next request instead of a stale cached instance."""
    return build_storage(get_settings())
