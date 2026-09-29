import pytest

from app.config import Settings
from app.storage import GcsStorage, LocalStorage, build_storage


async def test_local_storage_round_trip(tmp_path):
    storage = LocalStorage(str(tmp_path))
    await storage.save("42/report.pdf", b"hello", "application/pdf")
    assert await storage.open("42/report.pdf") == b"hello"
    await storage.delete("42/report.pdf")
    with pytest.raises(FileNotFoundError):
        await storage.open("42/report.pdf")


async def test_local_storage_open_missing_key_raises_file_not_found(tmp_path):
    storage = LocalStorage(str(tmp_path))
    with pytest.raises(FileNotFoundError):
        await storage.open("no/such/key")


def test_local_storage_rejects_a_key_that_escapes_the_base_dir(tmp_path):
    storage = LocalStorage(str(tmp_path))
    with pytest.raises(ValueError):
        storage._resolve("../../etc/passwd")


def test_build_storage_local_is_the_default():
    storage = build_storage(Settings())
    assert isinstance(storage, LocalStorage)


def test_build_storage_gcs_without_bucket_raises():
    with pytest.raises(RuntimeError):
        build_storage(Settings(ATTACHMENTS_BACKEND="gcs"))


class _FakeBlob:
    def __init__(self, store: dict, key: str):
        self._store = store
        self._key = key

    def upload_from_string(self, data: bytes, content_type: str) -> None:
        self._store[self._key] = data

    def download_as_bytes(self) -> bytes:
        from google.cloud.exceptions import NotFound

        if self._key not in self._store:
            raise NotFound(self._key)
        return self._store[self._key]

    def delete(self) -> None:
        from google.cloud.exceptions import NotFound

        if self._key not in self._store:
            raise NotFound(self._key)
        del self._store[self._key]


class _FakeBucket:
    def __init__(self):
        self.store: dict[str, bytes] = {}

    def blob(self, key: str) -> _FakeBlob:
        return _FakeBlob(self.store, key)


class _FakeClient:
    def __init__(self):
        self._bucket = _FakeBucket()

    def bucket(self, name: str) -> _FakeBucket:
        return self._bucket


async def test_gcs_storage_round_trip_with_a_mocked_client():
    client = _FakeClient()
    storage = GcsStorage("some-bucket", client=client)
    await storage.save("7/photo.png", b"bytes", "image/png")
    assert await storage.open("7/photo.png") == b"bytes"
    assert client._bucket.store["7/photo.png"] == b"bytes"
    await storage.delete("7/photo.png")
    with pytest.raises(FileNotFoundError):
        await storage.open("7/photo.png")


async def test_gcs_storage_open_missing_key_raises_file_not_found():
    storage = GcsStorage("some-bucket", client=_FakeClient())
    with pytest.raises(FileNotFoundError):
        await storage.open("missing")


async def test_gcs_storage_delete_missing_key_is_a_no_op():
    storage = GcsStorage("some-bucket", client=_FakeClient())
    await storage.delete("missing")  # doesn't raise
