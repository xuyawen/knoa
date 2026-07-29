"""knowledge 路由包共享工具：文档序列化 / 类型推断 / 标题提取。"""
from app.db import Document
from app.models.knowledge import DocumentOut

_TYPE_MAP = {
    "md": "MD",
    "markdown": "MD",
    "txt": "TXT",
    "docx": "DOCX",
    "pdf": "PDF",
    # Phase 7 多模态：图片/音频/视频的类型徽标
    "png": "IMAGE", "jpg": "IMAGE", "jpeg": "IMAGE", "gif": "IMAGE",
    "bmp": "IMAGE", "webp": "IMAGE",
    "mp3": "AUDIO", "wav": "AUDIO", "m4a": "AUDIO", "ogg": "AUDIO",
    "flac": "AUDIO", "aac": "AUDIO",
    "mp4": "VIDEO", "mov": "VIDEO", "webm": "VIDEO", "mkv": "VIDEO", "avi": "VIDEO",
}


def doc_type(source_path: str) -> str:
    """按文件名/存储 key 的扩展名推断文档类型（覆盖 md/txt/docx/pdf）。
    兼容 OSS 直传后的完整 URL（先取路径末段文件名，再取扩展名）。"""
    name = source_path.rsplit("/", 1)[-1]  # URL/key 末段文件名
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else "txt"
    return _TYPE_MAP.get(ext, "TXT")


def doc_out(d: Document) -> DocumentOut:
    """统一把 Document 行序列化成 DocumentOut（列表/上传/审核后共用）。"""
    return DocumentOut(
        id=str(d.id),
        title=d.title,
        type=doc_type(d.source_path),
        size_kb=round((d.file_size or len(d.content_md.encode("utf-8", errors="ignore"))) / 1024, 2),
        status=d.status,
        updated_at=d.updated_at.isoformat() if d.updated_at else "",
        original_filename=d.original_filename,
        file_size=d.file_size,
        category=d.category,
        department_id=str(d.department_id) if d.department_id else None,
        uploader_name=d.uploader_name,
        scope=d.scope,
        parse_status=d.parse_status,
    )


def extract_title(content: str, fallback: str) -> str:
    """取正文首个一级标题作为文档标题，没有则回退到文件名。"""
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return fallback
