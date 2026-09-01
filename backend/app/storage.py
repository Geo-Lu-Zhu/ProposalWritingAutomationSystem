"""Thin helpers around the on-disk JSON layout described in the app design.

Nothing here is a database: every "record" is a JSON file (or a directory of
JSON files) under backend/library or backend/projects. These helpers just
centralize path construction and safe read/write so routers don't scatter
raw file paths everywhere.
"""
import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from app.config import LIBRARY_DIR, LIBRARY_PAPERS_DIR, LIBRARY_TEMPLATES_DIR, PROJECTS_DIR


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with open(path, "r") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    tmp.replace(path)


def read_text(path: Path, default: str = "") -> str:
    if not path.exists():
        return default
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Library paths
# ---------------------------------------------------------------------------

def library_authors_path() -> Path:
    return LIBRARY_DIR / "authors.json"


def library_chunks_metadata_path() -> Path:
    return LIBRARY_DIR / "chunks_metadata.json"


def library_embeddings_path() -> Path:
    return LIBRARY_DIR / "embeddings.npy"


def library_faiss_index_path() -> Path:
    return LIBRARY_DIR / "faiss_index.bin"


def library_paper_dir(paper_id: str) -> Path:
    return LIBRARY_PAPERS_DIR / paper_id


def library_paper_source_path(paper_id: str) -> Path:
    return library_paper_dir(paper_id) / "source.pdf"


def library_paper_raw_text_path(paper_id: str) -> Path:
    return library_paper_dir(paper_id) / "raw_text.json"


def library_paper_citation_path(paper_id: str) -> Path:
    return library_paper_dir(paper_id) / "citation.json"


def list_library_paper_ids() -> list[str]:
    if not LIBRARY_PAPERS_DIR.exists():
        return []
    return sorted(p.name for p in LIBRARY_PAPERS_DIR.iterdir() if p.is_dir())


def library_template_path(name: str) -> Path:
    # name: "nofo_topics" | "section_outline"
    return LIBRARY_TEMPLATES_DIR / f"{name}.json"


# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------

def project_dir(project_id: str) -> Path:
    return PROJECTS_DIR / project_id


def project_meta_path(project_id: str) -> Path:
    return project_dir(project_id) / "meta.json"


def project_template_path(project_id: str, name: str) -> Path:
    return project_dir(project_id) / "templates" / f"{name}.json"


def project_nofo_dir(project_id: str) -> Path:
    return project_dir(project_id) / "nofo"


def project_ideas_dir(project_id: str) -> Path:
    return project_dir(project_id) / "ideas"


def project_ideas_rounds_dir(project_id: str) -> Path:
    return project_ideas_dir(project_id) / "rounds"


def project_drafting_dir(project_id: str) -> Path:
    return project_dir(project_id) / "drafting"


def project_section_dir(project_id: str, section_name: str) -> Path:
    safe = section_name.replace("/", "_")
    return project_drafting_dir(project_id) / "sections" / safe


def project_proposal_dir(project_id: str) -> Path:
    return project_dir(project_id) / "proposal"


def project_proposal_versions_dir(project_id: str) -> Path:
    return project_proposal_dir(project_id) / "versions"


def project_proposal_scores_dir(project_id: str) -> Path:
    return project_proposal_dir(project_id) / "scores"


def list_project_ids() -> list[str]:
    if not PROJECTS_DIR.exists():
        return []
    return sorted(p.name for p in PROJECTS_DIR.iterdir() if p.is_dir())


def delete_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
