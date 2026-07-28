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
import re
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass


class UnsupportedFormatError(ValueError):
    """格式不支持，或解析所需依赖缺失。"""


@dataclass
class ParseResult:
    text: str
    format: str  # 'md' | 'txt' | 'docx' | 'pdf'


def _decode(data: bytes) -> str:
    # 中文文档多为 utf-8 或 gbk/gb18030；逐级退回，最后才用 lossy 兜底。
    # 不用 charset_normalizer 自动探测：它对 CJK 字节常误判成其他编码（如 cp949）导致乱码。
    for enc in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


# ---- 提取后清洗（所有格式通用）----
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")  # 控制字符（保留 \n \t \r）
_WS_RE = re.compile(r"[\u00a0\u2000-\u200a\u202f\u205f\u3000]")  # 各类特殊空格 → 普通空格
_ZW_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")  # 零宽字符 / BOM → 删除


def clean_text(text: str) -> str:
    """归一化并清理提取出的原文：NFKC 字形统一、去控制字符/零宽、合并空行。"""
    text = unicodedata.normalize("NFKC", text)
    text = _CTRL_RE.sub("", text)
    text = _WS_RE.sub(" ", text)
    text = _ZW_RE.sub("", text)
    lines = [ln.rstrip() for ln in text.split("\n")]
    out: list[str] = []
    blank = 0
    for ln in lines:
        if ln == "":
            blank += 1
            if blank <= 2:  # 连续空行最多保留 2 个
                out.append(ln)
        else:
            blank = 0
            out.append(ln)
    return "\n".join(out).strip()


def _dedup_headers_footers(pages: list[str], min_ratio: float = 0.6, max_len: int = 60) -> list[str]:
    """剥掉跨页重复出现的页眉/页脚/页码行（同一行在 >=min_ratio 页里出现即视为页眉页脚）。"""
    n = len(pages)
    if n < 2:
        return pages
    page_lines = [p.split("\n") for p in pages]

    def _common(get_lines: callable) -> set[str]:  # type: ignore[valid-type]
        cnt: Counter = Counter()
        for pl in page_lines:
            for line in set(get_lines(pl)):  # 同页去重，避免一页多次出现抬升计数
                s = line.strip()
                if s and len(line) <= max_len:
                    cnt[line] += 1
        return {line for line, c in cnt.items() if c / n >= min_ratio}

    head_common = _common(lambda pl: pl[:3])
    foot_common = _common(lambda pl: pl[-3:])
    cleaned: list[str] = []
    for pl in page_lines:
        head = 0
        while head < len(pl) and pl[head].strip() in head_common:
            head += 1
        tail = len(pl)
        while tail > head and pl[tail - 1].strip() in foot_common:
            tail -= 1
        cleaned.append("\n".join(pl[head:tail]))
    return cleaned


def parse_markdown(filename: str, data: bytes) -> ParseResult:
    return ParseResult(clean_text(_decode(data)), "md")


def parse_text(filename: str, data: bytes) -> ParseResult:
    return ParseResult(clean_text(_decode(data)), "txt")


def parse_docx(filename: str, data: bytes) -> ParseResult:
    """用标准库解 OOXML：docx = zip，正文在 word/document.xml。"""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
            # ponytail: 防 zip bomb / 海量条目撑爆内存——限制条目数与单条目解压后大小
            if len(names) > 10_000:
                raise UnsupportedFormatError("文档条目数过多，疑似恶意压缩包，已拒绝解析")
            for info in zf.infolist():
                if info.file_size > 50 * 1024 * 1024:
                    raise UnsupportedFormatError("文档内单文件过大，疑似压缩炸弹，已拒绝解析")
            if "word/document.xml" in names:
                target = "word/document.xml"
            else:
                target = next((n for n in names if n.endswith("document.xml")), None)
            if target is None:
                raise UnsupportedFormatError("不是合法的 .docx（找不到 document.xml）")
            xml_data = zf.read(target)
            # 二次兜底：解压后正文超阈值直接拒绝
            if len(xml_data) > 50 * 1024 * 1024:
                raise UnsupportedFormatError("文档内容过大，疑似压缩炸弹，已拒绝解析")
    except zipfile.BadZipFile as e:
        raise UnsupportedFormatError("文件不是 zip 包，无法当作 .docx 解析") from e

    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    root = ET.fromstring(xml_data)
    paragraphs: list[str] = []
    for p in root.iter(f"{ns}p"):
        texts = [t.text or "" for t in p.iter(f"{ns}t")]
        paragraphs.append("".join(texts))
    return ParseResult(clean_text("\n".join(paragraphs)), "docx")


def parse_pdf(filename: str, data: bytes) -> ParseResult:
    """PDF 解析：优先 pymupdf(fitz) 引擎（中文/CJK 版式与字体映射远强于 pypdf），

    缺失时回退 pypdf；两者均缺失则给出清晰提示而非崩溃。"""
    MAX_PDF_TEXT = 50 * 1024 * 1024

    # 优先 pymupdf：对中文 PDF 的 ToUnicode 映射、版式保留远胜 pypdf，根治乱码错字
    try:
        import fitz  # pymupdf
    except ImportError:
        fitz = None
    if fitz is not None:
        try:
            doc = fitz.open(stream=data, filetype="pdf")
            try:
                if doc.page_count > 500:
                    raise UnsupportedFormatError("PDF 页数过多，已拒绝解析")
                pages: list[str] = [
                    clean_text(doc.load_page(i).get_text("text") or "")
                    for i in range(doc.page_count)
                ]
            finally:
                doc.close()
            pages = _dedup_headers_footers(pages)
            text = clean_text("\n".join(pages))
            if len(text) > MAX_PDF_TEXT:
                raise UnsupportedFormatError("PDF 文本内容过大，已拒绝解析")
            return ParseResult(text, "pdf")
        except UnsupportedFormatError:
            raise
        except Exception as e:  # noqa: BLE001 (intentional catch-all: fitz 解析异常兜底回退 pypdf)
            # fitz 解析失败（损坏/加密 PDF）时退回 pypdf 再试一次
            pass

    # 回退 pypdf
    try:
        from pypdf import PdfReader
    except ImportError:
        raise UnsupportedFormatError(
            "PDF 解析需要 pymupdf 或 pypdf。当前环境均未安装；"
            "请在部署环境执行 `pip install pymupdf` 后重试。"
        ) from None
    reader = PdfReader(io.BytesIO(data))
    # ponytail: 防恶意 PDF 撑爆内存——限制页数
    if len(reader.pages) > 500:
        raise UnsupportedFormatError("PDF 页数过多，已拒绝解析")
    # 逐页清洗 + 跨页去重页眉页脚，再整体清洗合并空行
    texts: list[str] = [clean_text(page.extract_text() or "") for page in reader.pages]
    texts = _dedup_headers_footers(texts)
    text = clean_text("\n".join(texts))
    if len(text) > MAX_PDF_TEXT:
        raise UnsupportedFormatError("PDF 文本内容过大，已拒绝解析")
    return ParseResult(text, "pdf")


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
