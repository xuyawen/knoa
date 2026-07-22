"""对象存储抽象层（Phase 3 T3 文档解析管线）。

为何存在：文档解析管线需要在 ingestion 之前保存「原始文件字节」（PDF/DOCX/MD），
以便溯源、重解析、审计。生产环境常用 MinIO/S3；但沙箱起不了 MinIO server，
且 venv 装不了官方 minio 客户端，于是自研一个**零依赖、可切换**的存储层：

- LocalObjectStore：直接落本地磁盘（app/data/uploads/），沙箱/开发默认，零依赖、可测。
- S3ObjectStore：用 httpx 直连 S3/MinIO REST + 手写 AWS SigV4 签名，
  不依赖 boto3/minio SDK，与本项目中「ES / 联网搜索都走 httpx 直连」的一贯风格一致。

通过 settings.OBJECT_STORE 切换（local | s3）。S3 路径仅在配置了真实端点且可达时才会被走到，
沙箱内默认走 local，因此整条管线在沙箱里即可端到端验证。
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import time
import urllib.parse
from abc import ABC, abstractmethod
from pathlib import Path

import httpx

from app.config import settings


class ObjectStore(ABC):
    """对象存储最小契约：按 key 存/取/删/查。"""

    @abstractmethod
    async def put(self, key: str, data: bytes) -> None: ...

    @abstractmethod
    async def get(self, key: str) -> bytes: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    async def exists(self, key: str) -> bool: ...


# ---------------------------------------------------------------------------
# 本地磁盘实现（默认，沙箱/开发可用，零依赖）
# ---------------------------------------------------------------------------
class LocalObjectStore(ObjectStore):
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # 防目录穿越：拒绝含 '..' 的片段，避免 key 写出 root 之外
        parts = [p for p in key.split("/") if p and p != "."]
        if any(p == ".." for p in parts):
            raise ValueError(f"非法 object key: {key}")
        return self.root.joinpath(*parts)

    async def put(self, key: str, data: bytes) -> None:
        p = self._path(key)
        await asyncio.to_thread(self._put_sync, p, data)

    async def get(self, key: str) -> bytes:
        p = self._path(key)
        return await asyncio.to_thread(p.read_bytes)

    async def delete(self, key: str) -> None:
        p = self._path(key)
        await asyncio.to_thread(self._delete_sync, p)

    async def exists(self, key: str) -> bool:
        p = self._path(key)
        return await asyncio.to_thread(p.exists)

    @staticmethod
    def _put_sync(p: Path, data: bytes) -> None:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    @staticmethod
    def _delete_sync(p: Path) -> None:
        if p.exists():
            p.unlink()


# ---------------------------------------------------------------------------
# AWS SigV4 手写签名（仅覆盖 S3 对象级 PUT/GET/HEAD/DELETE 最小子集）
# ---------------------------------------------------------------------------
def _hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _aws_sigv4_headers(
    method: str,
    url: str,
    region: str,
    access_key: str,
    secret_key: str,
    payload: bytes,
    *,
    service: str = "s3",
    extra_headers: dict | None = None,
) -> dict:
    """对一次 S3 请求生成 AWS SigV4 所需的 headers（含 Authorization）。

    仅实现对象级签名所需字段：host / x-amz-date / x-amz-content-sha256 + Authorization。
    不处理查询参数签名、chunked 上传等高级场景。
    """
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc
    path = parsed.path or "/"
    now = time.gmtime()
    amz_date = time.strftime("%Y%m%dT%H%M%SZ", now)
    date_stamp = time.strftime("%Y%m%d", now)
    payload_hash = _sha256_hex(payload)

    headers: dict[str, str] = {
        "host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
    }
    if extra_headers:
        headers.update(extra_headers)

    # canonical headers：按字典序、小写 key、trim 值，结尾带 \n
    canonical_headers = "".join(
        f"{k.lower()}:{str(v).strip()}\n" for k, v in sorted(headers.items())
    )
    signed_headers = ";".join(sorted(headers.keys())).lower()

    canonical_request = "\n".join(
        [method, path, "", canonical_headers, signed_headers, payload_hash]
    )
    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            _sha256_hex(canonical_request.encode("utf-8")),
        ]
    )

    k_date = _hmac_sha256(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    k_region = _hmac_sha256(k_date, region)
    k_service = _hmac_sha256(k_region, service)
    k_signing = _hmac_sha256(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    auth = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    headers["Authorization"] = auth
    return headers


# ---------------------------------------------------------------------------
# S3 / MinIO 实现（httpx 直连，零 SDK）
# ---------------------------------------------------------------------------
class S3ObjectStore(ObjectStore):
    """MinIO/S3 兼容对象存储（httpx + 手写 SigV4，不依赖任何 SDK）。"""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "us-east-1",
        use_ssl: bool = True,
        timeout: float = 10.0,
    ):
        self.endpoint = endpoint.rstrip("/")
        self.bucket = bucket
        self.region = region
        self.access_key = access_key
        self.secret_key = secret_key
        self.use_ssl = use_ssl
        self._client = httpx.AsyncClient(timeout=timeout)

    def _object_url(self, key: str) -> str:
        scheme = "https" if self.use_ssl else "http"
        return f"{scheme}://{self.endpoint}/{self.bucket}/{key}"

    def _sign(self, method: str, url: str, payload: bytes) -> dict:
        return _aws_sigv4_headers(
            method, url, self.region, self.access_key, self.secret_key, payload
        )

    async def put(self, key: str, data: bytes) -> None:
        url = self._object_url(key)
        headers = self._sign("PUT", url, data)
        headers["content-type"] = "application/octet-stream"
        resp = await self._client.put(url, content=data, headers=headers)
        resp.raise_for_status()

    async def get(self, key: str) -> bytes:
        url = self._object_url(key)
        headers = self._sign("GET", url, b"")
        resp = await self._client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.content

    async def delete(self, key: str) -> None:
        url = self._object_url(key)
        headers = self._sign("DELETE", url, b"")
        resp = await self._client.delete(url, headers=headers)
        resp.raise_for_status()

    async def exists(self, key: str) -> bool:
        url = self._object_url(key)
        headers = self._sign("HEAD", url, b"")
        resp = await self._client.head(url, headers=headers)
        return resp.status_code == 200

    async def aclose(self) -> None:
        await self._client.aclose()


# ---------------------------------------------------------------------------
# 工厂：按配置选择后端（带模块级单例缓存）
# ---------------------------------------------------------------------------
_store: ObjectStore | None = None


def _local_dir() -> Path:
    d = Path(settings.OBJECT_STORE_LOCAL_DIR)
    if not d.is_absolute():
        # 相对路径按项目根（backend/）解析，避免依赖启动时 cwd
        d = Path(__file__).resolve().parent.parent.parent / settings.OBJECT_STORE_LOCAL_DIR
    return d


def get_object_store() -> ObjectStore:
    global _store
    if _store is not None:
        return _store
    if settings.OBJECT_STORE == "s3":
        _store = S3ObjectStore(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            bucket=settings.MINIO_BUCKET,
            region=settings.MINIO_REGION,
            use_ssl=settings.MINIO_USE_SSL,
        )
    else:
        _store = LocalObjectStore(_local_dir())
    return _store


def reset_object_store() -> None:
    """测试用：清空单例，下次调用 get_object_store 重新构建。"""
    global _store
    _store = None
