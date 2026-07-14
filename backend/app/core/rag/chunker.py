import re


class MarkdownChunker:
    """按 markdown header 切分, 过长的段滑窗切。

    短文本保护: 低于 min_chunk_chars 视为噪声丢弃; 但若整篇都有实质内容,
    则至少保底一个 chunk, 避免短 FAQ / 零散笔记审核通过后搜不到。
    """

    def __init__(
        self,
        chunk_size: int = 500,
        overlap: int = 50,
        min_chunk_chars: int = 10,
    ):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.min_chunk_chars = min_chunk_chars

    def chunk(self, text: str, title: str) -> list[dict]:
        sections = self._split_by_headers(text)
        chunks = []
        idx = 0
        for section_title, section_text in sections:
            header = f"# {title}\n"
            if section_title:
                header += f"## {section_title}\n"
            full = header + section_text.strip()
            if self._is_noise(full):
                continue
            if len(full) > self.chunk_size:
                step = self.chunk_size - self.overlap
                for i in range(0, len(full), step):
                    chunk_text = full[i : i + self.chunk_size]
                    if self._is_noise(chunk_text):
                        # 滑窗尾部残片: 并入上一块, 不丢长文档尾巴
                        if chunks:
                            chunks[-1]["content"] += chunk_text
                        elif self._has_real_content(chunk_text):
                            chunks.append({"index": idx, "content": chunk_text})
                            idx += 1
                        continue
                    chunks.append({"index": idx, "content": chunk_text})
                    idx += 1
            else:
                chunks.append({"index": idx, "content": full})
                idx += 1
        # 文档级保底: 整篇都被当噪声丢弃时, 若原文确有内容则至少留一个 chunk
        if not chunks and self._has_real_content(text):
            stripped = text.strip()
            chunks.append({"index": 0, "content": f"# {title}\n{stripped}" if stripped else f"# {title}"})
        return chunks

    def _is_noise(self, s: str) -> bool:
        """strip 后字符数低于阈值视为噪声(空行/纯标点/极短碎片)。"""
        return len(s.strip()) < self.min_chunk_chars

    @staticmethod
    def _has_real_content(s: str) -> bool:
        """是否含至少一个实质字符(CJK / 字母 / 数字), 排除纯标点空白。"""
        return bool(re.search(r"[\w\u4e00-\u9fff]", s))

    def _split_by_headers(self, text: str) -> list[tuple[str, str]]:
        pattern = r"^(#{2,3})\s+(.+)$"
        sections = []
        current_title = ""
        current_text: list[str] = []
        for line in text.split("\n"):
            m = re.match(pattern, line)
            if m:
                if current_text:
                    sections.append((current_title, "\n".join(current_text)))
                current_title = m.group(2)
                current_text = []
            else:
                current_text.append(line)
        if current_text:
            sections.append((current_title, "\n".join(current_text)))
        return sections
