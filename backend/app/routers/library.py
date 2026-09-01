from fastapi import APIRouter, File, HTTPException, UploadFile

from app.jobs import set_progress, start_job
from app.models.schemas import AddAuthorsRequest, CitationUpdate, TemplateUpdateRequest
from app.services import library_service, templates_service

router = APIRouter(prefix="/library", tags=["library"])

_TEMPLATE_NAME_MAP = {"nofo-topics": "nofo_topics", "section-outline": "section_outline"}


def _resolve_template_name(name: str) -> str:
    if name not in _TEMPLATE_NAME_MAP:
        raise HTTPException(404, f"Unknown template '{name}'")
    return _TEMPLATE_NAME_MAP[name]


@router.get("/authors/search")
async def search_authors(q: str):
    if not q.strip():
        return []
    return await library_service.search_authors(q)


@router.get("/authors")
def list_authors():
    return library_service.list_authors()


@router.post("/authors")
async def add_authors(body: AddAuthorsRequest):
    selections = [{"author_id": a.author_id, "name": a.name} for a in body.authors]
    return await library_service.add_authors(selections)


@router.post("/papers")
async def upload_papers(files: list[UploadFile] = File(...)):
    payloads = [(f.filename, await f.read()) for f in files]

    async def run(job_id: str):
        results = []
        for i, (filename, data) in enumerate(payloads):
            set_progress(job_id, step="ingesting", file=filename, file_index=i + 1, file_count=len(payloads))
            result = await library_service.ingest_paper(filename, data)
            results.append(result)
        set_progress(job_id, step="done")
        return {"papers": results}

    job_id = start_job(run)
    return {"job_id": job_id}


@router.get("/papers")
def list_papers():
    return library_service.list_papers()


@router.get("/papers/unmatched")
def list_unmatched_papers():
    return library_service.list_unmatched_papers()


@router.patch("/papers/{paper_id}/citation")
def update_paper_citation(paper_id: str, body: CitationUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    return library_service.update_paper_citation(paper_id, updates)


@router.get("/templates/{name}")
def get_template(name: str):
    return templates_service.get_library_template(_resolve_template_name(name))


@router.put("/templates/{name}")
def set_template(name: str, body: TemplateUpdateRequest):
    return templates_service.set_library_template(_resolve_template_name(name), body.data)
