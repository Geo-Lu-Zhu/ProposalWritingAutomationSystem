import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BACKEND_DIR = Path(__file__).resolve().parent.parent
LIBRARY_DIR = BACKEND_DIR / "library"
PROJECTS_DIR = BACKEND_DIR / "projects"

LIBRARY_PAPERS_DIR = LIBRARY_DIR / "papers"
LIBRARY_TEMPLATES_DIR = LIBRARY_DIR / "templates"

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "")

MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_MODEL = "mistral-large-latest"
OPENAI_MODEL = "gpt-4o"

SEMANTIC_SCHOLAR_BASE_URL = "https://api.semanticscholar.org/graph/v1"

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

for d in (LIBRARY_PAPERS_DIR, LIBRARY_TEMPLATES_DIR, PROJECTS_DIR):
    d.mkdir(parents=True, exist_ok=True)
