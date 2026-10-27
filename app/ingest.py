# app/ingest.py
"""Load documents and decide add / update / duplicate.

load_document() turns PDF, DOCX or TXT/Markdown bytes into a LoadedDocument.
content_hash() fingerprints the text; save_document() uses it to skip duplicates
and to update a document when the same file name comes back with new content.
The chunkers (paragraph_chunks, fixed_chunks) go in this file too.
"""
import hashlib
import io
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

import docx
import psycopg
from docx.table import Table
from psycopg.types.json import Jsonb
from pypdf import PdfReader
from pypdf.errors import PyPdfError

SUPPORTED_FORMATS = {".pdf": "pdf", ".docx": "docx", ".txt": "txt", ".md": "md"}


class IngestError(ValueError):
    """A file we can't turn into text: wrong type, corrupt, encrypted or empty."""


@dataclass
class LoadedDocument:
    title: str
    text: str  # paragraphs separated by blank lines, headings start with "# "
    file_format: str  # "pdf", "docx", "txt" or "md"
    metadata: dict = field(default_factory=dict)  # file_name, format, page_count, author


# ---------- Loaders ----------

def load_document(filename: str, data: bytes) -> LoadedDocument:
    """Turn raw file bytes into a LoadedDocument (works for uploads and files on disk)."""
    file_format = SUPPORTED_FORMATS.get(Path(filename).suffix.lower())
    if file_format is None:
        raise IngestError(f"{filename}: unsupported file type (use PDF, DOCX, TXT or MD)")

    readers = {"pdf": _read_pdf, "docx": _read_docx, "txt": _read_text, "md": _read_text}
    try:
        text, meta_title, extra = readers[file_format](data)
    except IngestError as e:
        raise IngestError(f"{filename}: {e}") from None

    text = _clean(text)
    if not text:
        raise IngestError(f"{filename}: no text found (scanned PDF or empty file?)")

    title = meta_title or _first_heading(text) or _title_from_name(filename)
    metadata = {"file_name": Path(filename).name, "format": file_format, **extra}
    metadata = {k: v for k, v in metadata.items() if v not in (None, "")}  # keep only what exists
    return LoadedDocument(title=title.strip(), text=text, file_format=file_format, metadata=metadata)


def load_file(path: str | Path) -> LoadedDocument:
    """Convenience for scripts: load a file from disk."""
    path = Path(path)
    return load_document(path.name, path.read_bytes())


def _read_pdf(data: bytes) -> tuple[str, str | None, dict]:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise IngestError("PDF is password-protected")
        pages = [page.extract_text() or "" for page in reader.pages]
        info = reader.metadata  # None when the PDF has no info dictionary
    except PyPdfError as e:
        raise IngestError(f"cannot read PDF ({e})") from e
    title = info.title if info else None
    author = info.author if info else None
    return "\n\n".join(pages), title, {"page_count": len(pages), "author": author}


def _read_docx(data: bytes) -> tuple[str, str | None, dict]:
    try:
        document = docx.Document(io.BytesIO(data))
    except (zipfile.BadZipFile, KeyError) as e:
        raise IngestError("not a valid DOCX file") from e

    blocks = []
    for item in document.iter_inner_content():  # paragraphs and tables, in document order
        if isinstance(item, Table):
            rows = [" | ".join(cell.text.strip() for cell in row.cells) for row in item.rows]
            blocks.append("\n".join(rows))  # one table = one block
            continue
        text = item.text.strip()
        if not text:
            continue
        style = item.style.name if item.style is not None else ""
        if style.startswith("Heading") or style == "Title":
            text = "# " + text  # same heading marker as Markdown, so one chunker rule covers both
        blocks.append(text)

    props = document.core_properties
    return "\n\n".join(blocks), props.title, {"author": props.author}


def _read_text(data: bytes) -> tuple[str, str | None, dict]:
    try:
        return data.decode("utf-8-sig"), None, {}  # "-sig" drops a BOM if there is one
    except UnicodeDecodeError as e:
        raise IngestError("text file is not UTF-8") from e


def _clean(text: str) -> str:
    """Unix line endings, no trailing spaces, at most one blank line between paragraphs."""
    text = text.replace("\x00", "")  # Postgres text columns reject NUL bytes (some PDFs contain them)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _first_heading(text: str) -> str | None:
    for line in text.split("\n"):
        if line.startswith("# "):
            return line[2:]
    return None


def _title_from_name(filename: str) -> str:
    return Path(filename).stem.replace("_", " ").replace("-", " ")


# ---------- Duplicates and updates ----------

def normalize_text(text: str) -> str:
    """Collapse every run of whitespace (spaces, tabs, newlines) to one space and trim the ends.
    Only for hashing: stored text keeps its blank lines, because the chunkers need them."""
    return " ".join(text.split())


def content_hash(text: str) -> str:
    """SHA-256 of the normalized text, as 64 hex characters. Same hash = duplicate document."""
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def save_document(conn: psycopg.Connection, doc: LoadedDocument, source: str,
                  protected: bool = False) -> tuple[str, UUID]:
    """Write the documents row and report what happened.

    ("duplicate", id): this content is already stored; nothing written.
    ("updated", id):   same source + file name, new content; row updated, version + 1,
                       old chunks deleted. Insert the new chunks next.
    ("added", id):     new document. Insert its chunks next.

    Call it inside `with conn.transaction():` and insert the chunks in the same
    transaction, so if the chunk insert fails the old chunks come back.
    """
    digest = content_hash(doc.text)
    file_name = doc.metadata["file_name"]

    row = conn.execute("SELECT id FROM documents WHERE content_hash = %s", (digest,)).fetchone()
    if row:
        return "duplicate", row[0]

    row = conn.execute(
        "SELECT id FROM documents WHERE source = %s AND external_id = %s",
        (source, file_name),
    ).fetchone()
    if row:
        doc_id = row[0]
        conn.execute(
            """UPDATE documents
               SET title = %s, file_format = %s, content_hash = %s, metadata = %s,
                   version = version + 1, updated_at = now()
               WHERE id = %s""",
            (doc.title, doc.file_format, digest, Jsonb(doc.metadata), doc_id),
        )
        conn.execute("DELETE FROM chunks WHERE document_id = %s", (doc_id,))
        return "updated", doc_id

    row = conn.execute(
        """INSERT INTO documents
               (source, external_id, title, file_format, content_hash, is_protected, metadata)
           VALUES (%s, %s, %s, %s, %s, %s, %s)
           RETURNING id""",
        (source, file_name, doc.title, doc.file_format, digest, protected, Jsonb(doc.metadata)),
    ).fetchone()
    return "added", row[0]