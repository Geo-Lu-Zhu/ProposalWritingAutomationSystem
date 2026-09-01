import re
from datetime import datetime, timezone

from app.services import library_service, templates_service
from app.services.llm import mistral_chat, openai_chat, safe_json_parse
from app.services.pdf import chunk_text, extract_text_from_pdf
from app.services.vector_store import ChunkIndex
from app.storage import (
    list_project_ids,
    new_id,
    project_dir,
    project_ideas_dir,
    project_ideas_rounds_dir,
    project_meta_path,
    project_nofo_dir,
    read_json,
    write_json,
    write_text,
)

NOFO_SOURCE_FILENAME = "source.pdf"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Project lifecycle
# ---------------------------------------------------------------------------

def list_projects() -> list[dict]:
    projects = [read_json(project_meta_path(pid), default={}) for pid in list_project_ids()]
    projects.sort(key=lambda p: p.get("created_at", ""), reverse=True)
    return projects


def get_project(project_id: str) -> dict:
    meta = read_json(project_meta_path(project_id), default=None)
    if meta is None:
        raise FileNotFoundError(f"Project {project_id} not found")
    return meta


def _save_meta(meta: dict) -> dict:
    meta["updated_at"] = _now()
    write_json(project_meta_path(meta["id"]), meta)
    return meta


def _archive_currently_active() -> None:
    for pid in list_project_ids():
        meta = read_json(project_meta_path(pid), default={})
        if meta.get("status") == "active":
            meta["status"] = "archived"
            _save_meta(meta)


def create_project(name: str, nofo_filename: str, nofo_bytes: bytes, nofo_topics_override, section_outline_override) -> dict:
    _archive_currently_active()

    project_id = new_id()
    project_dir(project_id).mkdir(parents=True, exist_ok=True)
    (project_nofo_dir(project_id)).mkdir(parents=True, exist_ok=True)
    (project_nofo_dir(project_id) / NOFO_SOURCE_FILENAME).write_bytes(nofo_bytes)

    templates_service.seed_project_templates(project_id, nofo_topics_override, section_outline_override)

    meta = {
        "id": project_id,
        "name": name or nofo_filename,
        "status": "active",
        "current_stage": "setup",
        "nofo_filename": nofo_filename,
        "created_at": _now(),
    }
    return _save_meta(meta)


def archive_project(project_id: str) -> dict:
    meta = get_project(project_id)
    meta["status"] = "archived"
    return _save_meta(meta)


def reopen_project(project_id: str) -> dict:
    _archive_currently_active()
    meta = get_project(project_id)
    meta["status"] = "active"
    return _save_meta(meta)


def set_project_stage(project_id: str, stage: str) -> dict:
    meta = get_project(project_id)
    meta["current_stage"] = stage
    return _save_meta(meta)


# ---------------------------------------------------------------------------
# NOFO ingestion
# ---------------------------------------------------------------------------

def _nofo_index(project_id: str) -> ChunkIndex:
    d = project_nofo_dir(project_id)
    return ChunkIndex(d / "faiss_index.bin", d / "chunks_metadata.json")


def _requirements_path(project_id: str):
    return project_nofo_dir(project_id) / "requirements.json"


async def _extract_requirements_for_topic(project_id: str, topic: str) -> dict:
    index = _nofo_index(project_id)
    results = await index.search(topic, k=6)
    nofo_text = "\n\n".join(r["chunk"] for r in results)

    prompt = f"""
You are an NIH grant reviewer. Extract ONLY structured JSON from the NOFO text.

STRICT RULES:
- RETURN ONLY A VALID JSON OBJECT.
- NO explanatory text. NO markdown. NO comments. NO trailing commas.

JSON FORMAT TO RETURN:
{{
  "topic": "...",
  "requirements": ["...", "..."],
  "risk_of_noncompliance": ["...", "..."]
}}

EXTRACT FROM NOFO TEXT BELOW:
\"\"\"{nofo_text}\"\"\"
"""
    raw = await openai_chat(
        [
            {"role": "system", "content": "You return ONLY valid JSON. No explanation. No markdown."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
    )
    data = safe_json_parse(raw)
    data.setdefault("topic", topic)
    return data


async def ingest_nofo(project_id: str, progress_cb=None) -> dict:
    """Extract -> chunk -> embed the NOFO, then extract structured requirements per topic."""
    source_path = project_nofo_dir(project_id) / NOFO_SOURCE_FILENAME

    if progress_cb:
        progress_cb(step="extracting_text")
    nofo_text = extract_text_from_pdf(source_path)
    write_text(project_nofo_dir(project_id) / "raw_text.txt", nofo_text)

    if progress_cb:
        progress_cb(step="chunking_and_embedding")
    chunks = chunk_text(nofo_text, min_len=200, max_len=1200)
    index = _nofo_index(project_id)
    await index.add_chunks(chunks, [{"source": "NOFO"} for _ in chunks])

    topics = templates_service.get_project_template(project_id, "nofo_topics")
    requirements: dict[str, dict] = {}
    for i, topic in enumerate(topics):
        if progress_cb:
            progress_cb(step="extracting_requirements", topic=topic, topic_index=i + 1, topic_count=len(topics))
        requirements[topic] = await _extract_requirements_for_topic(project_id, topic)

    write_json(_requirements_path(project_id), requirements)
    set_project_stage(project_id, "idea")

    if progress_cb:
        progress_cb(step="done")
    return {"chunk_count": len(chunks), "requirements": requirements}


def get_nofo_requirements(project_id: str) -> dict:
    return read_json(_requirements_path(project_id), default={})


# ---------------------------------------------------------------------------
# Idea generation, selection, iterative refinement
# ---------------------------------------------------------------------------

def _candidates_path(project_id: str):
    return project_ideas_dir(project_id) / "candidates.json"


def _selected_path(project_id: str):
    return project_ideas_dir(project_id) / "selected.json"


def _idea_specific_chunks_path(project_id: str):
    return project_ideas_dir(project_id) / "idea_specific_chunks.json"


async def generate_idea_candidates(project_id: str) -> dict:
    requirements = get_nofo_requirements(project_id)

    prompt = f"""
You are an NIH grant strategist developing research concepts for the funding
opportunity described below.

=== NOFO REQUIREMENTS ===
{requirements}

Generate 10 innovative, scientifically coherent, technically feasible research ideas
grounded in this funding opportunity.

Return ONLY a valid JSON array, no markdown, in this exact form:
[
  {{"title": "...", "rationale": "...", "methods": "...", "impact": "..."}},
  ...
]
"""
    raw = await mistral_chat([{"role": "user", "content": prompt}], temperature=0.4)
    parsed = safe_json_parse(raw)
    ideas = parsed if isinstance(parsed, list) else parsed.get("raw_text", [])
    if not isinstance(ideas, list):
        ideas = []

    candidates = [{"index": i, **idea} for i, idea in enumerate(ideas)]

    rec_prompt = f"""
You are an NIH study section reviewer. Select the BEST research idea from the set below.

=== NOFO REQUIREMENTS ===
{requirements}

=== CANDIDATE IDEAS (JSON) ===
{candidates}

Return ONLY valid JSON: {{"recommended_index": <int>, "reason": "..."}}
"""
    rec_raw = await openai_chat([{"role": "user", "content": rec_prompt}], temperature=0.0)
    recommendation = safe_json_parse(rec_raw)

    data = {"candidates": candidates, "recommendation": recommendation, "generated_at": _now()}
    write_json(_candidates_path(project_id), data)
    return data


def get_idea_candidates(project_id: str) -> dict:
    return read_json(_candidates_path(project_id), default={})


def _idea_rounds(project_id: str) -> list[dict]:
    rounds_dir = project_ideas_rounds_dir(project_id)
    if not rounds_dir.exists():
        return []
    files = sorted(rounds_dir.glob("*.json"), key=lambda p: int(p.stem))
    return [read_json(f) for f in files]


def _save_idea_round(project_id: str, round_data: dict) -> dict:
    rounds = _idea_rounds(project_id)
    n = len(rounds)
    write_json(project_ideas_rounds_dir(project_id) / f"{n}.json", round_data)
    return round_data


def select_idea(project_id: str, candidate_index: int) -> dict:
    candidates = get_idea_candidates(project_id).get("candidates", [])
    match = next((c for c in candidates if c["index"] == candidate_index), None)
    if match is None:
        raise ValueError(f"No candidate with index {candidate_index}")

    round_data = {"type": "select", "candidate_index": candidate_index, "idea_text": match, "created_at": _now()}
    return _save_idea_round(project_id, round_data)


async def revise_idea(project_id: str, comment: str) -> dict:
    rounds = _idea_rounds(project_id)
    if not rounds:
        raise ValueError("No idea has been selected yet.")
    current_idea = rounds[-1]["idea_text"]

    prompt = f"""
You are revising a single NIH research idea based on user feedback.
Keep it grounded, feasible, and specific. Return ONLY valid JSON in the same shape:
{{"title": "...", "rationale": "...", "methods": "...", "impact": "..."}}

CURRENT IDEA:
{current_idea}

USER FEEDBACK:
{comment}
"""
    raw = await mistral_chat([{"role": "user", "content": prompt}], temperature=0.3)
    revised = safe_json_parse(raw)
    revised["index"] = current_idea.get("index")

    round_data = {"type": "revise", "comment": comment, "idea_text": revised, "created_at": _now()}
    return _save_idea_round(project_id, round_data)


async def confirm_idea(project_id: str) -> dict:
    from app.services.citation_registry import ProjectCitations

    rounds = _idea_rounds(project_id)
    if not rounds:
        raise ValueError("No idea has been selected yet.")
    final_idea = rounds[-1]["idea_text"]

    write_json(_selected_path(project_id), {"idea": final_idea, "confirmed_at": _now(), "rounds": len(rounds)})

    query_text = f"{final_idea.get('title', '')} {final_idea.get('rationale', '')}"
    index = library_service.get_index()
    results = await index.search(query_text, k=50)
    write_json(_idea_specific_chunks_path(project_id), results)

    reg = ProjectCitations(project_id)
    for r in results:
        reg.register(str(r.get("citation_id", r["id"])), {
            "title": r.get("title", "Unknown Title"),
            "authors": r.get("authors", "Unknown Authors"),
            "year": r.get("year", "n.d."),
            "venue": r.get("venue", ""),
            "doi": r.get("doi", ""),
        })
    reg.save()

    set_project_stage(project_id, "drafting")
    return {"idea": final_idea, "idea_specific_chunk_count": len(results)}


def get_selected_idea(project_id: str) -> dict | None:
    return read_json(_selected_path(project_id), default=None)


def get_idea_rounds(project_id: str) -> list[dict]:
    return _idea_rounds(project_id)
