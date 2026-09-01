import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.jobs import set_progress, start_job
from app.models.schemas import IdeaReviseRequest, IdeaSelectRequest, ProposalReviseRequest, ScoreRequest, TemplateUpdateRequest
from app.services import draft_service, project_service, templates_service

router = APIRouter(prefix="/projects", tags=["projects"])

_TEMPLATE_NAME_MAP = {"nofo-topics": "nofo_topics", "section-outline": "section_outline"}


def _resolve_template_name(name: str) -> str:
    if name not in _TEMPLATE_NAME_MAP:
        raise HTTPException(404, f"Unknown template '{name}'")
    return _TEMPLATE_NAME_MAP[name]


def _get_or_404(project_id: str) -> dict:
    try:
        return project_service.get_project(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("")
def list_projects():
    return project_service.list_projects()


@router.post("")
async def create_project(
    name: str = Form(""),
    nofo_file: UploadFile = File(...),
    nofo_topics: str | None = Form(None),
    section_outline: str | None = Form(None),
):
    topics_override = json.loads(nofo_topics) if nofo_topics else None
    outline_override = json.loads(section_outline) if section_outline else None

    nofo_bytes = await nofo_file.read()
    meta = project_service.create_project(name, nofo_file.filename, nofo_bytes, topics_override, outline_override)

    async def run(job_id: str):
        def progress_cb(**kwargs):
            set_progress(job_id, **kwargs)

        return await project_service.ingest_nofo(meta["id"], progress_cb=progress_cb)

    job_id = start_job(run)
    return {"project": meta, "job_id": job_id}


@router.post("/{project_id}/archive")
def archive_project(project_id: str):
    _get_or_404(project_id)
    return project_service.archive_project(project_id)


@router.post("/{project_id}/reopen")
def reopen_project(project_id: str):
    _get_or_404(project_id)
    return project_service.reopen_project(project_id)


@router.get("/{project_id}")
def get_project(project_id: str):
    return _get_or_404(project_id)


@router.get("/{project_id}/templates/{name}")
def get_project_template(project_id: str, name: str):
    _get_or_404(project_id)
    return templates_service.get_project_template(project_id, _resolve_template_name(name))


@router.put("/{project_id}/templates/{name}")
def set_project_template(project_id: str, name: str, body: TemplateUpdateRequest):
    _get_or_404(project_id)
    return templates_service.set_project_template(project_id, _resolve_template_name(name), body.data)


@router.get("/{project_id}/nofo/requirements")
def get_nofo_requirements(project_id: str):
    _get_or_404(project_id)
    return project_service.get_nofo_requirements(project_id)


# ---------------------------------------------------------------------------
# Idea generation / selection / refinement
# ---------------------------------------------------------------------------

@router.post("/{project_id}/ideas/generate")
async def generate_ideas(project_id: str):
    _get_or_404(project_id)
    return await project_service.generate_idea_candidates(project_id)


@router.get("/{project_id}/ideas")
def get_ideas(project_id: str):
    _get_or_404(project_id)
    return {
        "candidates": project_service.get_idea_candidates(project_id),
        "rounds": project_service.get_idea_rounds(project_id),
        "selected": project_service.get_selected_idea(project_id),
    }


@router.post("/{project_id}/ideas/select")
def select_idea(project_id: str, body: IdeaSelectRequest):
    _get_or_404(project_id)
    try:
        return project_service.select_idea(project_id, body.candidate_index)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{project_id}/ideas/revise")
async def revise_idea(project_id: str, body: IdeaReviseRequest):
    _get_or_404(project_id)
    try:
        return await project_service.revise_idea(project_id, body.comment)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{project_id}/ideas/confirm")
async def confirm_idea(project_id: str):
    _get_or_404(project_id)
    try:
        return await project_service.confirm_idea(project_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


# ---------------------------------------------------------------------------
# Drafting / proposal
# ---------------------------------------------------------------------------

@router.post("/{project_id}/draft/start")
def start_drafting(project_id: str):
    _get_or_404(project_id)

    async def run(job_id: str):
        def progress_cb(**kwargs):
            set_progress(job_id, **kwargs)

        return await draft_service.run_drafting_loop(project_id, progress_cb=progress_cb)

    job_id = start_job(run)
    return {"job_id": job_id}


@router.get("/{project_id}/draft/sections")
def get_section_drafts(project_id: str):
    _get_or_404(project_id)
    return draft_service.get_section_drafts(project_id)


@router.get("/{project_id}/proposal")
def get_proposal(project_id: str):
    _get_or_404(project_id)
    proposal = draft_service.get_current_proposal(project_id)
    if proposal is None:
        raise HTTPException(404, "No proposal has been drafted yet.")
    return proposal


@router.get("/{project_id}/proposal/versions")
def list_proposal_versions(project_id: str):
    _get_or_404(project_id)
    return draft_service.list_versions(project_id)


@router.get("/{project_id}/proposal/versions/{version}")
def get_proposal_version(project_id: str, version: int):
    _get_or_404(project_id)
    return draft_service.get_proposal_version(project_id, version)


@router.post("/{project_id}/proposal/revise")
async def revise_proposal(project_id: str, body: ProposalReviseRequest):
    _get_or_404(project_id)
    try:
        return await draft_service.revise_proposal(project_id, body.feedback)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{project_id}/proposal/score")
async def score_proposal(project_id: str, body: ScoreRequest):
    _get_or_404(project_id)
    try:
        return await draft_service.score_proposal(project_id, body.version)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
