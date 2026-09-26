from pathlib import Path
import fitz


def extract_pdf_text(path: str | Path) -> str:
    path = Path(path)
    parts: list[str] = []
    with fitz.open(path) as doc:
        for page in doc:
            text = page.get_text("text")
            if text.strip():
                parts.append(text)
    return "\n".join(parts)
