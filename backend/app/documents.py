from io import BytesIO
from pathlib import Path
from fastapi import UploadFile, HTTPException
from pypdf import PdfReader
from docx import Document
from PIL import Image
import pytesseract

ALLOWED = {".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg", ".webp"}

async def extract_text(upload: UploadFile, max_bytes: int) -> str:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(415, "Unsupported file type. Upload PDF, DOCX, TXT or an image.")
    raw = await upload.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise HTTPException(413, "Uploaded file exceeds the size limit.")
    try:
        if suffix == ".pdf":
            text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(raw)).pages)
        elif suffix == ".docx":
            doc = Document(BytesIO(raw))
            text = "\n".join(p.text for p in doc.paragraphs)
            for table in doc.tables:
                text += "\n" + "\n".join(" | ".join(c.text for c in row.cells) for row in table.rows)
        elif suffix == ".txt":
            text = raw.decode("utf-8-sig")
        else:
            try:
                text = pytesseract.image_to_string(Image.open(BytesIO(raw)))
            except Exception as exc:
                raise HTTPException(422, "Image OCR unavailable. Install Tesseract and retry.") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, "Could not read uploaded document.") from exc
    if not text.strip():
        raise HTTPException(422, "No readable text was found.")
    return text[:100_000]
