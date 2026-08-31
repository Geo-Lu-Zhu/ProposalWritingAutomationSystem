"""Semantic Scholar lookups + LLM-title fuzzy matching (ported from the notebook).

Two Semantic Scholar use sites:
- author search, used in the Library UI so the user can disambiguate and
  pick the right author(s) by looking at their most-cited papers
- author's full paper list, used to build the "master citations" match
  target once an author is selected
"""
import asyncio
import re
import time
from difflib import SequenceMatcher

import requests

from app.config import SEMANTIC_SCHOLAR_BASE_URL
from app.services.llm import mistral_chat

AUTHOR_SEARCH_FIELDS = "name,affiliations,paperCount,citationCount,hIndex,papers.title,papers.year,papers.citationCount"
AUTHOR_PAPERS_FIELDS = "title,year,venue,authors,externalIds,url,abstract,publicationTypes"


def _search_authors_sync(query: str, limit: int = 10) -> list[dict]:
    url = f"{SEMANTIC_SCHOLAR_BASE_URL}/author/search"
    resp = requests.get(url, params={"query": query, "fields": AUTHOR_SEARCH_FIELDS, "limit": limit}, timeout=30)
    resp.raise_for_status()
    data = resp.json().get("data", [])

    results = []
    for a in data:
        papers = sorted(a.get("papers", []), key=lambda p: p.get("citationCount") or 0, reverse=True)
        top_papers = [
            {"title": p.get("title", ""), "year": p.get("year"), "citationCount": p.get("citationCount") or 0}
            for p in papers[:5]
        ]
        results.append(
            {
                "author_id": a.get("authorId", ""),
                "name": a.get("name", ""),
                "affiliations": a.get("affiliations", []),
                "paper_count": a.get("paperCount") or 0,
                "citation_count": a.get("citationCount") or 0,
                "h_index": a.get("hIndex") or 0,
                "top_papers": top_papers,
            }
        )
    return results


async def search_authors(query: str, limit: int = 10) -> list[dict]:
    return await asyncio.to_thread(_search_authors_sync, query, limit)


def _get_author_papers_sync(author_id: str, limit: int = 1000) -> list[dict]:
    url = f"{SEMANTIC_SCHOLAR_BASE_URL}/author/{author_id}/papers"
    params = {"fields": AUTHOR_PAPERS_FIELDS, "limit": limit, "offset": 0}

    all_papers: list[dict] = []
    while True:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        papers = data.get("data", [])
        if not papers:
            break
        all_papers.extend(papers)
        if len(papers) < limit:
            break
        params["offset"] += limit
        time.sleep(0.5)

    return all_papers


async def get_author_papers(author_id: str) -> list[dict]:
    return await asyncio.to_thread(_get_author_papers_sync, author_id)


def normalize_paper(p: dict) -> dict:
    authors = ", ".join(a.get("name", "") for a in p.get("authors", []))
    doi = (p.get("externalIds") or {}).get("DOI", "")
    venue = p.get("venue") or "Unknown Venue"
    return {
        "paper_id": p.get("paperId", ""),
        "title": p.get("title", ""),
        "year": p.get("year", ""),
        "venue": venue,
        "doi": doi,
        "authors": authors,
    }


def _normalize_title(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _fuzzy(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def match_title_against_master(llm_title: str, master_index: list[dict], threshold: float = 0.65) -> dict | None:
    """master_index entries need a 'title_norm' key (see normalize_paper + _normalize_title)."""
    llm_norm = _normalize_title(llm_title)

    best = None
    best_score = 0.0
    for entry in master_index:
        score = _fuzzy(llm_norm, entry["title_norm"])
        if score > best_score:
            best, best_score = entry, score

    return best if best_score >= threshold else None


async def llm_extract_title(intro_text: str) -> str:
    prompt = f"""
    Extract ONLY the scientific paper title from the text below.
    Return only the title. No quotes. No extra text.

    TEXT:
    {intro_text[:600]}
    """
    resp = await mistral_chat([{"role": "user", "content": prompt}], temperature=0.0)
    title = resp.strip().replace("\n", " ").strip()

    if len(title) < 5 or len(title.split()) < 2:
        lines = [l.strip() for l in intro_text.split("\n") if len(l.strip()) > 6]
        return max(lines, key=len) if lines else "Untitled Document"

    return title


def is_duplicate_title(title: str, existing_titles: list[str], threshold: float = 0.92) -> bool:
    norm = _normalize_title(title)
    return any(_fuzzy(norm, _normalize_title(t)) >= threshold for t in existing_titles)
