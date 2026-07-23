"""阿里云 OSS 前端直传签名（PostObject，零 SDK）。

为什么手写不引 SDK：与本项目 storage.py（S3 走 httpx + 手写 SigV4）一贯风格一致——
OSS PostObject 签名只是一次 HMAC-SHA1，标准库即可完成，无需 ali-oss / aliyun-python-sdk。

流程：
  1. 前端调后端 /api/oss/sign 拿 policy( base64) + signature + host + key
  2. 前端用 FormData 把 {key, OSSAccessKeyId, policy, signature,
     success_action_status, file} POST 到 host
  3. OSS 返回 200/204 即成功，文件 URL = {host}/{key}

参考：阿里云 OSS PostObject（https://help.aliyun.com/zh/oss/developer-reference/post-object/）
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass

from app.config import settings


@dataclass
class OssSignResult:
    access_key_id: str
    policy: str          # base64 后的 policy JSON
    signature: str       # base64 后的 HMAC-SHA1 签名
    host: str            # https://{bucket}.{endpoint}
    key: str             # 对象 key（含前缀 + 日期目录 + uuid 防重名）
    url: str             # 文件可访问地址 {host}/{key}
    expires_at: int      # 签名过期时间戳（秒）


def _hmac_sha1(key: str, msg: str) -> bytes:
    return hmac.new(key.encode("utf-8"), msg.encode("utf-8"), hashlib.sha1).digest()


def build_sign(prefix: str, filename: str, expire_seconds: int = 600) -> OssSignResult:
    """生成一次 PostObject 直传所需的签名与上传参数。

    prefix: 对象 key 前缀（如 uploads/docs、uploads/chat），用于隔离不同业务文件。
    filename: 原始文件名（仅用于拼 key 防重名，不强制保留中文名，url 编码交给浏览器）。
    """
    if not (settings.OSS_BUCKET and settings.OSS_ENDPOINT
            and settings.OSS_ACCESS_KEY_ID and settings.OSS_ACCESS_KEY_SECRET):
        raise RuntimeError("OSS 未配置：请在 .env 设置 OSS_BUCKET/OSS_ENDPOINT/OSS_ACCESS_KEY_ID/OSS_ACCESS_KEY_SECRET")

    expire_at = int(time.time()) + expire_seconds
    # OSS policy expiration 用 ISO8601 GMT，毫秒 .000Z 结尾
    expiration_iso = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(expire_at))
    date_dir = time.strftime("%Y/%m/%d", time.gmtime())

    # key 含 uuid 防重名；filename 原样拼（含扩展名），空格/中文由浏览器 FormData 自动编码
    safe_name = filename.replace("/", "_").replace("\\", "_") or "file"
    key = f"{prefix}/{date_dir}/{uuid.uuid4().hex}_{safe_name}"

    policy_dict = {
        "expiration": expiration_iso,
        "conditions": [
            {"bucket": settings.OSS_BUCKET},
            # 限制 key 必须以指定前缀开头，防止前端篡改写到别处
            ["starts-with", "$key", prefix],
            # 单文件大小上限
            ["content-length-range", 0, settings.OSS_MAX_SIZE],
        ],
    }
    policy_b64 = base64.b64encode(json.dumps(policy_dict).encode("utf-8")).decode("ascii")
    signature = base64.b64encode(_hmac_sha1(settings.OSS_ACCESS_KEY_SECRET, policy_b64)).decode("ascii")

    host = f"https://{settings.OSS_BUCKET}.{settings.OSS_ENDPOINT}"
    return OssSignResult(
        access_key_id=settings.OSS_ACCESS_KEY_ID,
        policy=policy_b64,
        signature=signature,
        host=host,
        key=key,
        url=f"{host}/{key}",
        expires_at=expire_at,
    )


def is_oss_url(value: str) -> bool:
    """粗略判断字符串是否本 OSS 桶的文件 URL（用于 upload_document 区分 URL / base64）。"""
    if not settings.OSS_BUCKET or not settings.OSS_ENDPOINT:
        return False
    host = f"https://{settings.OSS_BUCKET}.{settings.OSS_ENDPOINT}"
    return value.startswith(host + "/")


def normalize_url(value: str) -> str:
    """校验 OSS URL 合法性（防 SSRF：只允许指向本桶 host）。"""
    if not is_oss_url(value):
        raise ValueError("非法的 OSS 文件地址")
    return value


def b64url_to_b64(encoded: str) -> str:
    """OSS 返回/前端传回的 base64 可能因 url-safe 字符需规整（保留以备扩展）。"""
    try:
        # 先试标准 base64
        base64.b64decode(encoded, validate=True)
        return encoded
    except binascii.Error:
        # 兜底转 standard 字母表
        return encoded.replace("-", "+").replace("_", "/")
