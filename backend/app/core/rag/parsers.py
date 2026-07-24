"""文档解析器（Phase 3 T3 文档解析管线）。

RAG 系统真实的摄入源大多是 PDF/DOCX，而不是 markdown。本模块把「原始字节 -> 纯文本」
这一步从 ingestor 中抽出来，做成**可按扩展名分发的解析器注册表**。

沙箱约束（venv 装不了第三方包）：
- .md / .txt：直接当文本，零依赖。
- .docx：OOXML 本质是个 zip 包，用标准库 zipfile + xml.etree 抽取 word/document.xml 文本，
  零依赖、可离线测试。
- .pdf：需要 pypdf（纯 Python）。沙箱 venv 里没有这个包，所以做成
  「有则用之、无则报清晰错误」——部署到有 pypdf 的环境即自动生效，不引入硬依赖。
"""
from __future__ import annotations

import io
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass


class UnsupportedFormatError(ValueError):
    """格式不支持，或解析所需依赖缺失。"""


@dataclass
class ParseResult:
    text: str
    format: str  # 'md' | 'txt' | 'docx' | 'pdf'


def _decode(data: bytes) -> str:
    # markdown/txt 多为 utf-8；逐级退回宽松解码，避免整篇因编码问题失败
    for enc in ("utf-8", "utf-8-sig", "gbk"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def parse_markdown(filename: str, data: bytes) -> ParseResult:
    return ParseResult(_decode(data), "md")


def parse_text(filename: str, data: bytes) -> ParseResult:
    return ParseResult(_decode(data), "txt")


def parse_docx(filename: str, data: bytes) -> ParseResult:
    """用标准库解 OOXML：docx = zip，正文在 word/document.xml。"""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
            if "word/document.xml" in names:
                target = "word/document.xml"
            else:
                target = next((n for n in names if n.endswith("document.xml")), None)
            if target is None:
                raise UnsupportedFormatError("不是合法的 .docx（找不到 document.xml）")
            xml_data = zf.read(target)
            # 防御 zip bomb：解压后正文超阈值直接拒绝，避免恶意 docx 撑爆内存
            if len(xml_data) > 50 * 1024 * 1024:
                raise UnsupportedFormatError("文档内容过大，疑似压缩炸弹，已拒绝解析")
    except zipfile.BadZipFile:
        raise UnsupportedFormatError("文件不是 zip 包，无法当作 .docx 解析")

    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    root = ET.fromstring(xml_data)
    paragraphs: list[str] = []
    for p in root.iter(f"{ns}p"):
        texts = [t.text or "" for t in p.iter(f"{ns}t")]
        paragraphs.append("".join(texts))
    return ParseResult("\n".join(paragraphs), "docx")


def parse_pdf(filename: str, data: bytes) -> ParseResult:
    """PDF 解析依赖 pypdf（纯 Python）。缺失时给出清晰提示而非崩溃。"""
    try:
        from pypdf import PdfReader
    except ImportError:
        raise UnsupportedFormatError(
            "PDF 解析需要 pypdf（纯 Python）。当前环境未安装；"
            "请在部署环境执行 `pip install pypdf` 后重试。"
        )
    reader = PdfReader(io.BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    return ParseResult("\n".join(pages), "pdf")


_PARSERS = {
    "md": parse_markdown,
    "markdown": parse_markdown,
    "txt": parse_text,
    "docx": parse_docx,
    "pdf": parse_pdf,
}


def parse_document(filename: str, data: bytes) -> ParseResult:
    """按扩展名分发到对应解析器。未知格式抛 UnsupportedFormatError。"""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    parser = _PARSERS.get(ext)
    if parser is None:
        raise UnsupportedFormatError(
            f"不支持的文件格式 .{ext or '未知'}，当前支持：md / txt / docx / pdf"
        )
    return parser(filename, data)
