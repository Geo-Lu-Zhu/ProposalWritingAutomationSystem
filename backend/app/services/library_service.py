import re

from app.services import citations
from app.services.pdf import chunk_text, extract_intro_text, extract_text_from_pdf
from app.services.vector_store import ChunkIndex
from app.storage import (
    library_authors_path,
    library_chunks_metadata_path,
    library_faiss_index_path,
    library_paper_citation_path,
    library_paper_dir,
    library_paper_raw_text_path,
    library_paper_source_path,
    library_template_path,  # noqa: F401  (re-exported for convenience elsewhere)
    list_library_paper_ids,
    new_id,
    read_json,
    write_json,
    write_text,
)


def _norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def get_index() -> ChunkIndex:
    return ChunkIndex(library_faiss_index_path(), library_chunks_metadata_path())


# ---------------------------------------------------------------------------
# Authors
# ---------------------------------------------------------------------------

def list_authors() -> list[dict]:
    return read_json(library_authors_path(), default=[])


async def search_authors(query: str) -> list[dict]:
    return await citations.search_authors(query)


async def add_authors(author_selections: list[dict]) -> list[dict]:
    """author_selections: [{author_id, name}, ...] picked from search results."""
    existing = list_authors()
    existing_ids = {a["author_id"] for a in existing}

    for sel in author_selections:
        if sel["author_id"] not in existing_ids:
            existing.append({"author_id": sel["author_id"], "name": sel.get("name", "")})
            existing_ids.add(sel["author_id"])

    write_json(library_authors_path(), existing)
    await _rebuild_master_citations(existing)
    return existing


async def _rebuild_master_citations(authors: list[dict]) -> list[dict]:
    all_papers: list[dict] = []
    seen_ids: set[str] = set()

    for author in authors:
        raw = await citations.get_author_papers(author["author_id"])
        for p in raw:
            norm = citations.normalize_paper(p)
            if norm["paper_id"] and norm["paper_id"] in seen_ids:
                continue
            seen_ids.add(norm["paper_id"])
            norm["title_norm"] = _norm_title(norm["title"])
            all_papers.append(norm)

    from app.config import LIBRARY_DIR

    write_json(LIBRARY_DIR / "master_citations.json", all_papers)
    return all_papers


def get_master_citation_index() -> list[dict]:
    from app.config import LIBRARY_DIR

    return read_json(LIBRARY_DIR / "master_citations.json", default=[])


# ---------------------------------------------------------------------------
# Papers
# ---------------------------------------------------------------------------

def list_papers() -> list[dict]:
    papers = []
    for paper_id in list_library_paper_ids():
        citation = read_json(library_paper_citation_path(paper_id), default={})
        papers.append({"paper_id": paper_id, **citation})
    return papers


def list_unmatched_papers() -> list[dict]:
    return [p for p in list_papers() if p.get("status") == "unmatched"]


def _existing_titles() -> list[str]:
    return [p.get("title", "") for p in list_papers() if p.get("title")]


async def ingest_paper(filename: str, pdf_bytes: bytes) -> dict:
    """Full per-paper pipeline: save -> extract -> title -> dedup -> match -> chunk -> embed.

    Any failure partway through removes the paper directory rather than leaving an
    incomplete entry (PDF saved, no citation.json) visible in the library.
    """
    import shutil

    paper_id = new_id()
    paper_dir = library_paper_dir(paper_id)
    paper_dir.mkdir(parents=True, exist_ok=True)

    try:
        source_path = library_paper_source_path(paper_id)
        source_path.write_bytes(pdf_bytes)

        intro = extract_intro_text(source_path)
        llm_title = await citations.llm_extract_title(intro)

        if citations.is_duplicate_title(llm_title, _existing_titles()):
            shutil.rmtree(paper_dir, ignore_errors=True)
            return {"paper_id": None, "status": "duplicate_skipped", "title": llm_title}

        full_text = extract_text_from_pdf(source_path)
        write_text(library_paper_raw_text_path(paper_id), full_text)

        master_index = get_master_citation_index()
        match = citations.match_title_against_master(llm_title, master_index)

        if match:
            citation = {
                "status": "matched",
                "title": match["title"],
                "authors": match["authors"],
                "year": match["year"],
                "venue": match["venue"],
                "doi": match["doi"],
                "source_file": filename,
            }
        else:
            citation = {
                "status": "unmatched",
                "title": llm_title or "Unknown Title",
                "authors": "Unknown Authors",
                "year": "n.d.",
                "venue": "",
                "doi": "",
                "source_file": filename,
            }

        write_json(library_paper_citation_path(paper_id), citation)

        chunks = chunk_text(full_text)
        chunk_meta = [
            {
                "citation_id": paper_id,
                "source": filename,
                "title": citation["title"],
                "authors": citation["authors"],
                "year": citation["year"],
                "venue": citation["venue"],
                "doi": citation["doi"],
            }
            for _ in chunks
        ]

        index = get_index()
        await index.add_chunks(chunks, chunk_meta)
    except Exception:
        shutil.rmtree(paper_dir, ignore_errors=True)
        raise

    return {"paper_id": paper_id, "status": citation["status"], "title": citation["title"], "chunk_count": len(chunks)}


def update_paper_citation(paper_id: str, updates: dict) -> dict:
    citation = read_json(library_paper_citation_path(paper_id), default={})
    citation.update(updates)
    citation["status"] = "manual"
    write_json(library_paper_citation_path(paper_id), citation)

    # Keep the chunk index metadata in sync so downstream RAG/citations reflect the fix.
    index = get_index()
    changed = False
    for entry in index.metadata:
        if entry.get("citation_id") == paper_id:
            entry["title"] = citation.get("title", entry.get("title"))
            entry["authors"] = citation.get("authors", entry.get("authors"))
            entry["year"] = citation.get("year", entry.get("year"))
            entry["venue"] = citation.get("venue", entry.get("venue"))
            entry["doi"] = citation.get("doi", entry.get("doi"))
            changed = True
    if changed:
        write_json(index.metadata_path, index.metadata)

    return citation
