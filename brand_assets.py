from __future__ import annotations

import hashlib
import io
import json
import mimetypes
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

try:
    from pypdf import PdfReader  # type: ignore
except Exception:
    PdfReader = None


TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".json",
    ".csv",
    ".tsv",
    ".yaml",
    ".yml",
    ".html",
    ".htm",
    ".xml",
    ".css",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".svg",
}

RICH_TEXT_EXTENSIONS = {
    ".pdf",
    ".docx",
}

TEXT_MIME_PREFIXES = (
    "text/",
    "application/json",
    "application/xml",
    "image/svg+xml",
)


def _slugify(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "default"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(filename: str) -> str:
    filename = (filename or "").strip().replace("\\", "/").split("/")[-1]
    filename = re.sub(r"[^A-Za-z0-9._-]+", "_", filename)
    return filename or "asset.bin"


def _looks_textual(filename: str, mime_type: str) -> bool:
    filename = filename or ""
    mime_type = (mime_type or "").lower().strip()
    if Path(filename).suffix.lower() in TEXT_EXTENSIONS | RICH_TEXT_EXTENSIONS:
        return True
    return any(mime_type.startswith(prefix) for prefix in TEXT_MIME_PREFIXES)


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return data.decode(encoding)
        except Exception:
            continue
    return ""


def _extract_pdf_text(data: bytes) -> str:
    if not data:
        return ""
    if PdfReader is None:
        return ""
    try:
        reader = PdfReader(io.BytesIO(data))
        chunks: List[str] = []
        for page in reader.pages:
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            if text.strip():
                chunks.append(text.strip())
        return "\n\n".join(chunks).strip()
    except Exception:
        return ""


def _extract_docx_text(data: bytes) -> str:
    if not data:
        return ""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = [name for name in zf.namelist() if name.startswith("word/") and name.endswith(".xml")]
            text_blocks: List[str] = []
            namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            for name in names:
                if not any(key in name for key in ("document.xml", "header", "footer")):
                    continue
                raw = zf.read(name)
                root = ET.fromstring(raw)
                for paragraph in root.findall(".//w:p", namespace):
                    parts = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
                    paragraph_text = "".join(parts).strip()
                    if paragraph_text:
                        text_blocks.append(paragraph_text)
            return "\n".join(text_blocks).strip()
    except Exception:
        return ""


def _extract_rich_text(filename: str, mime_type: str, data: bytes) -> str:
    suffix = Path(filename or "").suffix.lower()
    mime = (mime_type or "").lower().strip()
    if suffix == ".pdf" or mime == "application/pdf":
        return _extract_pdf_text(data)
    if suffix == ".docx" or mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return _extract_docx_text(data)
    if suffix in TEXT_EXTENSIONS or any(mime.startswith(prefix) for prefix in TEXT_MIME_PREFIXES):
        return _decode_text(data)
    return ""


@dataclass
class SavedBrandAsset:
    manifest_entry: Dict[str, Any]
    extracted_text: str = ""
    saved_path: str = ""


class BrandAssetStore:
    """
    Vault persistente por instancia.
    Conserva archivos originales, texto extraído y un manifest versionado.
    """

    def __init__(self, base_dir: str, instance_name: str):
        self.instance_slug = _slugify(instance_name)
        self.root = Path(base_dir).expanduser() / self.instance_slug
        self.raw_dir = self.root / "raw"
        self.extracted_dir = self.root / "processed"
        self.manifest_path = self.root / "manifest.json"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.extracted_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_manifest()

    def _ensure_manifest(self) -> None:
        if self.manifest_path.exists():
            return
        self._write_manifest(
            {
                "version": 1,
                "instance_slug": self.instance_slug,
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
                "assets": [],
            }
        )

    def _read_manifest(self) -> Dict[str, Any]:
        try:
            return json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return {
                "version": 1,
                "instance_slug": self.instance_slug,
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
                "assets": [],
            }

    def _write_manifest(self, data: Dict[str, Any]) -> None:
        data["updated_at"] = _now_iso()
        self.manifest_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def save_text_note(
        self,
        label: str,
        text: str,
        *,
        source: str = "admin_text",
        category: str = "knowledge",
        mime_type: str = "text/plain",
    ) -> SavedBrandAsset:
        content = (text or "").strip()
        if not content:
            return SavedBrandAsset(manifest_entry={}, extracted_text="", saved_path="")

        filename = _safe_name(f"{_slugify(label)}.txt")
        raw_path = self.raw_dir / filename
        raw_path.write_text(content, encoding="utf-8")

        extracted_path = self.extracted_dir / f"{raw_path.stem}.txt"
        extracted_path.write_text(content, encoding="utf-8")

        sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        entry = {
            "id": sha[:12],
            "filename": filename,
            "category": category,
            "source": source,
            "mime_type": mime_type,
            "raw_path": str(raw_path),
            "extracted_path": str(extracted_path),
            "bytes": len(content.encode("utf-8")),
            "words": len(content.split()),
            "sha256": sha,
            "created_at": _now_iso(),
            "textual": True,
        }
        manifest = self._read_manifest()
        manifest.setdefault("assets", []).append(entry)
        self._write_manifest(manifest)
        return SavedBrandAsset(entry, extracted_text=content, saved_path=str(raw_path))

    def save_binary_asset(
        self,
        *,
        filename: str,
        data: bytes,
        mime_type: str = "",
        source: str = "admin_attachment",
        category: str = "asset",
        caption: str = "",
    ) -> SavedBrandAsset:
        safe_name = _safe_name(filename)
        raw_path = self.raw_dir / safe_name
        raw_path.write_bytes(data)

        guessed_mime = mime_type or mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
        extracted_text = _extract_rich_text(safe_name, guessed_mime, data)
        textual = bool(extracted_text.strip()) or _looks_textual(safe_name, guessed_mime)
        extracted_path = ""
        if extracted_text:
            extracted_path = str(self.extracted_dir / f"{raw_path.stem}.txt")
            Path(extracted_path).write_text(extracted_text, encoding="utf-8")

        sha = hashlib.sha256(data).hexdigest()
        entry = {
            "id": sha[:12],
            "filename": safe_name,
            "category": category,
            "source": source,
            "mime_type": guessed_mime,
            "raw_path": str(raw_path),
            "extracted_path": extracted_path,
            "bytes": len(data),
            "words": len(extracted_text.split()) if extracted_text else 0,
            "sha256": sha,
            "caption": (caption or "").strip(),
            "created_at": _now_iso(),
            "textual": textual,
        }
        manifest = self._read_manifest()
        manifest.setdefault("assets", []).append(entry)
        self._write_manifest(manifest)
        return SavedBrandAsset(entry, extracted_text=extracted_text, saved_path=str(raw_path))

    def manifest(self) -> Dict[str, Any]:
        return self._read_manifest()

    def clear(self) -> None:
        if self.root.exists():
            for child in sorted(self.root.rglob("*"), reverse=True):
                if child.is_file():
                    child.unlink(missing_ok=True)
                elif child.is_dir():
                    try:
                        child.rmdir()
                    except OSError:
                        pass
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.extracted_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_manifest()

    def summary_lines(self, limit: int = 6) -> List[str]:
        manifest = self._read_manifest()
        assets = manifest.get("assets", [])
        lines = [
            f"Vault: {self.root}",
            f"Assets: {len(assets)}",
        ]
        for item in assets[-limit:]:
            line = f"- {item.get('filename', 'asset')} · {item.get('category', 'asset')}"
            if item.get("caption"):
                line += f" · {item['caption'][:60]}"
            lines.append(line)
        return lines

    def latest_identity_summary(self, limit: int = 5) -> str:
        manifest = self._read_manifest()
        assets = manifest.get("assets", [])
        if not assets:
            return ""
        snippets = []
        for item in assets[-limit:]:
            filename = item.get("filename", "asset")
            category = item.get("category", "asset")
            caption = (item.get("caption") or "").strip()
            snippets.append(f"{filename} [{category}]{': ' + caption if caption else ''}")
        return "Activos de marca cargados: " + " | ".join(snippets)
