import re

from app.services import library_service, project_service, templates_service
from app.services.citation_registry import ProjectCitations
from app.services.llm import mistral_chat, openai_chat, safe_json_parse
from app.storage import (
    project_drafting_dir,
    project_proposal_dir,
    project_proposal_versions_dir,
    project_section_dir,
    read_json,
    write_json,
    write_text,
)

NIH_SYSTEM_PROMPT = """
You are an expert NIH grant writer.

Your role:
- Generate highly technical, NIH-compliant proposal sections.
- Always follow NIH Research Strategy structure.
- Maintain strict scientific tone.
- Use concise, analytic sentences.
- Integrate NOFO requirements faithfully.
- Use only the evidence provided in RAG context.
- Cite research numerically like [1], [2].
- Never fabricate citations.

Every section you write must:
- Be directly responsive to the NOFO.
- Present a clear logic and research rationale.
- Avoid marketing, hype, or vague statements.
- Include no fluff, only scientific justification.
"""


def _format_evidence(chunks: list[dict], citation_map: dict[str, int]) -> str:
    if not chunks:
        return "No relevant prior evidence found."
    lines = []
    for ch in chunks:
        cid = str(ch.get("citation_id", ch.get("id")))
        num = citation_map.get(cid, "?")
        lines.append(f"[{num}] (Source: {ch.get('source', '')})\n{ch.get('chunk', '')}\n")
    return "\n".join(lines)


def _nofo_context_block(project_id: str, nofo_topics: list[str]) -> str:
    requirements = project_service.get_nofo_requirements(project_id)
    block = ""
    for topic in nofo_topics:
        data = requirements.get(topic)
        if not data:
            block += f"\n# {topic}\n(no data found)\n"
            continue
        block += f"\n# NOFO TOPIC: {topic}\n"
        if data.get("requirements"):
            block += "Requirements:\n" + "\n".join(f"- {r}" for r in data["requirements"]) + "\n"
        if data.get("risk_of_noncompliance"):
            block += "Risks:\n" + "\n".join(f"- {r}" for r in data["risk_of_noncompliance"]) + "\n"
    return block


async def _draft_section(project_id: str, section: dict, idea_title: str, reg: ProjectCitations) -> str:
    query = f"{section['query']} focused on: {idea_title}"
    results = await library_service.get_index().search(query, k=6)

    citation_map: dict[str, int] = {}
    for r in results:
        cid = str(r.get("citation_id", r["id"]))
        num = reg.register(cid, {
            "title": r.get("title", "Unknown Title"),
            "authors": r.get("authors", "Unknown Authors"),
            "year": r.get("year", "n.d."),
            "venue": r.get("venue", ""),
            "doi": r.get("doi", ""),
        })
        citation_map[cid] = num

    evidence_block = _format_evidence(results, citation_map)
    nofo_block = _nofo_context_block(project_id, section.get("nofo_topics", []))
    word_limit = section.get("word_limit")
    length_instruction = (
        f"WORD LIMIT: {word_limit} words. Stay under this limit.\n"
        if word_limit
        else "Produce full, concise NIH-style content (roughly 1500-3000 words).\n"
    )

    idea = project_service.get_selected_idea(project_id) or {}
    idea_text = idea.get("idea", {})

    user_prompt = f"""
Write the **{section['name']}** section of an NIH proposal.
{length_instruction}

=== CITATION SOURCES (USE THESE NUMBERS ONLY) ===
{reg.citation_map_text()}

=== RESEARCH IDEA (Selected) ===
{idea_text}

=== EVIDENCE (RAG Extracts) ===
{evidence_block}

=== NOFO REQUIREMENTS ===
{nofo_block}

INSTRUCTIONS:
- Ensure the section uniquely contributes to the proposal.
- Use numeric citations like [3], [12], matching the sources above.
- Do NOT hallucinate sources.
- Use 2-5 well-structured NIH-style paragraphs.
"""
    draft = await mistral_chat(
        [{"role": "system", "content": NIH_SYSTEM_PROMPT}, {"role": "user", "content": user_prompt}],
        temperature=0.25,
    )
    reg.sync_from_text(draft)
    return draft


async def _review_section(section_name: str, draft: str) -> dict:
    prompt = f"""
You are an NIH scientific review officer. Evaluate the following draft section:

SECTION: {section_name}
TEXT:
{draft}

Provide scores (1=best, 9=worst) and constructive comments.

Return JSON:
{{
  "score_significance": ...,
  "score_innovation": ...,
  "score_approach": ...,
  "strengths": "...",
  "weaknesses": "..."
}}
"""
    raw = await openai_chat([{"role": "user", "content": prompt}], temperature=0.0)
    return safe_json_parse(raw)


async def _revise_section(draft: str, feedback: dict, reg: ProjectCitations) -> str:
    prompt = f"""
You are revising a single NIH proposal section based on reviewer feedback.

Rules:
- DO NOT change citation numbers like [1], [2], [10].
- DO NOT invent citations.
- Maintain structure and meaning; improve clarity.

ORIGINAL SECTION:
{draft}

REVIEWER FEEDBACK:
{feedback}

Rewrite the section. Return ONLY the revised section text.
"""
    revised = await mistral_chat([{"role": "user", "content": prompt}], temperature=0.2)
    reg.sync_from_text(revised)
    return revised.strip()


async def run_drafting_loop(project_id: str, progress_cb=None) -> dict:
    outline = templates_service.get_project_template(project_id, "section_outline")
    idea = project_service.get_selected_idea(project_id) or {}
    idea_title = (idea.get("idea") or {}).get("title", "")

    reg = ProjectCitations(project_id)
    sections: dict[str, str] = {}

    for i, section in enumerate(outline):
        name = section["name"]
        if progress_cb:
            progress_cb(step="drafting", section=name, section_index=i + 1, section_count=len(outline))
        draft = await _draft_section(project_id, section, idea_title, reg)
        write_text(project_section_dir(project_id, name) / "first_draft.txt", draft)
        reg.save()

        if progress_cb:
            progress_cb(step="reviewing", section=name, section_index=i + 1, section_count=len(outline))
        feedback = await _review_section(name, draft)
        write_json(project_section_dir(project_id, name) / "reviewer_feedback.json", feedback)

        if progress_cb:
            progress_cb(step="revising", section=name, section_index=i + 1, section_count=len(outline))
        revised = await _revise_section(draft, feedback, reg)
        write_text(project_section_dir(project_id, name) / "revised_draft.txt", revised)
        reg.save()

        sections[name] = revised

    if progress_cb:
        progress_cb(step="combining")
    version = _save_new_version(project_id, sections, reg, created_from="auto", feedback_used=None)

    if progress_cb:
        progress_cb(step="scoring")
    await score_proposal(project_id)

    project_service.set_project_stage(project_id, "proposal")
    if progress_cb:
        progress_cb(step="done")
    return {"version": version}


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------

def _list_version_numbers(project_id: str) -> list[int]:
    versions_dir = project_proposal_versions_dir(project_id)
    if not versions_dir.exists():
        return []
    return sorted(int(p.name) for p in versions_dir.iterdir() if p.is_dir() and p.name.isdigit())


def _latest_version_number(project_id: str) -> int | None:
    versions = _list_version_numbers(project_id)
    return versions[-1] if versions else None


def _version_dir(project_id: str, version: int):
    return project_proposal_versions_dir(project_id) / str(version)


def _save_new_version(project_id: str, sections: dict[str, str], reg: ProjectCitations, created_from: str, feedback_used: str | None) -> int:
    from datetime import datetime, timezone

    version = (_latest_version_number(project_id) or 0) + 1
    vdir = _version_dir(project_id, version)

    full_text = "\n\n".join(f"## {name}\n\n{text}" for name, text in sections.items())
    references = reg.reference_list_text()
    full_text_with_refs = full_text + "\n\n## References\n\n" + references

    write_json(vdir / "sections.json", sections)
    write_text(vdir / "full_text.txt", full_text_with_refs)
    write_text(vdir / "references.txt", references)
    write_json(vdir / "meta.json", {
        "version": version,
        "created_from": created_from,
        "feedback_used": feedback_used,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return version


def get_section_drafts(project_id: str) -> list[dict]:
    outline = templates_service.get_project_template(project_id, "section_outline")
    result = []
    for section in outline:
        d = project_section_dir(project_id, section["name"])
        first_draft = (d / "first_draft.txt").read_text() if (d / "first_draft.txt").exists() else None
        revised_draft = (d / "revised_draft.txt").read_text() if (d / "revised_draft.txt").exists() else None
        reviewer_feedback = read_json(d / "reviewer_feedback.json", default=None)
        result.append({
            "name": section["name"],
            "first_draft": first_draft,
            "reviewer_feedback": reviewer_feedback,
            "revised_draft": revised_draft,
        })
    return result


def get_current_proposal(project_id: str) -> dict | None:
    version = _latest_version_number(project_id)
    if version is None:
        return None
    return get_proposal_version(project_id, version)


def get_proposal_version(project_id: str, version: int) -> dict:
    vdir = _version_dir(project_id, version)
    sections = read_json(vdir / "sections.json", default={})
    references = (vdir / "references.txt").read_text() if (vdir / "references.txt").exists() else ""
    meta = read_json(vdir / "meta.json", default={})
    score = get_score_for_version(project_id, version)
    return {"version": version, "sections": sections, "references": references, "meta": meta, "score": score}


def list_versions(project_id: str) -> list[dict]:
    return [read_json(_version_dir(project_id, v) / "meta.json") for v in _list_version_numbers(project_id)]


SECTION_HEADER_RE = lambda name: re.compile(rf"##\s*{re.escape(name)}\s*(.*?)(?=##|\Z)", re.DOTALL)


async def revise_proposal(project_id: str, feedback: str) -> dict:
    current = get_current_proposal(project_id)
    if current is None:
        raise ValueError("No proposal has been drafted yet.")

    outline = templates_service.get_project_template(project_id, "section_outline")
    section_names = [s["name"] for s in outline]

    full_text = "\n\n".join(f"## {name}\n{current['sections'].get(name, '[Missing section]')}\n" for name in section_names)

    base_feedback = """
You are performing a FINAL NIH-style proposal revision. Revise the ENTIRE proposal:

1. Strengthen the overall narrative so every section supports the core research idea.
2. CITATION ACCURACY: preserve all numeric citations exactly as written (e.g., [1], [2], [10]).
   Do NOT add, delete, change, or renumber any citations.
3. Remove redundant/repetitive text across sections while keeping all essential scientific/methodological content.
4. Improve clarity, flow, and NIH writing style.
"""
    full_feedback = base_feedback + (f"\n\nUSER-SPECIFIC FEEDBACK:\n{feedback}" if feedback.strip() else "")

    messages = [
        {"role": "system", "content": "You are a senior NIH proposal writer. Produce a polished, compliant, concise revision of the FULL proposal."},
        {"role": "user", "content": f"""
FULL PROPOSAL (to revise):
{full_text}

REVISION INSTRUCTIONS:
{full_feedback}

Return the COMPLETE revised proposal using the SAME EXACT section headers: {", ".join(section_names)}.
"""},
    ]
    revised_text = await mistral_chat(messages, temperature=0.2)
    revised_text = _clean_llm_output(revised_text)

    reg = ProjectCitations(project_id)
    reg.sync_from_text(revised_text)
    reg.save()

    sections = {}
    for name in section_names:
        match = SECTION_HEADER_RE(name).search(revised_text)
        sections[name] = match.group(1).strip() if match else current["sections"].get(name, "[Missing section]")

    version = _save_new_version(project_id, sections, reg, created_from="revision", feedback_used=feedback)
    return get_proposal_version(project_id, version)


def _clean_llm_output(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```.*?\n", "", t)
        t = t.rstrip("`").rstrip()
    t = re.sub(r"^Here is.*?\n", "", t, flags=re.IGNORECASE)
    return t.strip()


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _scores_path(project_id: str):
    return project_proposal_dir(project_id) / "scores.json"


def _all_scores(project_id: str) -> list[dict]:
    return read_json(_scores_path(project_id), default=[])


def get_score_for_version(project_id: str, version: int) -> dict | None:
    matches = [s for s in _all_scores(project_id) if s["version"] == version]
    return matches[-1] if matches else None


async def score_proposal(project_id: str, version: int | None = None) -> dict:
    version = version or _latest_version_number(project_id)
    if version is None:
        raise ValueError("No proposal version to score.")

    proposal = get_proposal_version(project_id, version)
    full_text = "\n\n".join(f"## {name}\n{text}" for name, text in proposal["sections"].items())

    system_prompt = """
You are an NIH peer review panel. Provide structured scoring for the FULL proposal.

Return ONLY valid JSON with this EXACT structure:
{
    "section_scores": {"Significance": <1-9>, "Innovation": <1-9>, "Approach": <1-9>},
    "overall_impact": <1-9>,
    "strengths": "<paragraph>",
    "weaknesses": "<paragraph>",
    "summary_statement": "<paragraph>"
}
Rules: integers 1-9 (1=exceptional, 9=poor). All fields must appear. NO extra text outside JSON.
"""
    raw = await openai_chat(
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": full_text}],
        temperature=0.0,
    )
    report = safe_json_parse(raw)

    from datetime import datetime, timezone

    entry = {"version": version, "report": report, "created_at": datetime.now(timezone.utc).isoformat()}
    scores = _all_scores(project_id)
    scores.append(entry)
    write_json(_scores_path(project_id), scores)
    return entry
