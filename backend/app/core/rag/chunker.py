import re


class MarkdownChunker:
    """按 markdown header 切分, 过长的段滑窗切"""

    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str, title: str) -> list[dict]:
        sections = self._split_by_headers(text)
        chunks = []
        idx = 0
        for section_title, section_text in sections:
            header = f"# {title}\n"
            if section_title:
                header += f"## {section_title}\n"
            full = header + section_text.strip()
            if len(full) > self.chunk_size:
                step = self.chunk_size - self.overlap
                for i in range(0, len(full), step):
                    chunk_text = full[i : i + self.chunk_size]
                    if len(chunk_text.strip()) > 50:
                        chunks.append({"index": idx, "content": chunk_text})
                        idx += 1
            else:
                if len(full.strip()) > 50:
                    chunks.append({"index": idx, "content": full})
                    idx += 1
        return chunks

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
