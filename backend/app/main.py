from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import jobs, library, projects

app = FastAPI(title="Proposal Writing Automation System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(library.router)
app.include_router(projects.router)
app.include_router(jobs.router)


@app.get("/health")
def health():
    return {"status": "ok"}
