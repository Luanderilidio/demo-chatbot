"""Caminho compartilhado da base, usado na ingestão e nas consultas.

No Windows, o índice HNSW pode falhar ao abrir caminhos com acentos.
Configure RAG_CHROMA_DIR ou informe o caminho em config/chroma_path.txt.
Os documentos ficam em dados/documentos, separados do banco vetorial.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DOCUMENTS_DIR = BASE_DIR / "dados" / "documentos"
PATH_FILE = BASE_DIR / "config" / "chroma_path.txt"

configured_path = os.environ.get("RAG_CHROMA_DIR", "").strip()
if not configured_path and PATH_FILE.is_file():
    configured_path = PATH_FILE.read_text(encoding="utf-8-sig").strip()

CHROMA_DIR = Path(configured_path).expanduser() if configured_path else BASE_DIR / "dados" / "chroma_db"
if not CHROMA_DIR.is_absolute():
    CHROMA_DIR = BASE_DIR / CHROMA_DIR
