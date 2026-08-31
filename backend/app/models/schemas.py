from typing import Any, Optional

from pydantic import BaseModel


class AuthorSelection(BaseModel):
    author_id: str
    name: str = ""


class AddAuthorsRequest(BaseModel):
    authors: list[AuthorSelection]


class CitationUpdate(BaseModel):
    title: Optional[str] = None
    authors: Optional[str] = None
    year: Optional[str] = None
    venue: Optional[str] = None
    doi: Optional[str] = None


class TemplateUpdateRequest(BaseModel):
    data: list[Any]


class IdeaSelectRequest(BaseModel):
    candidate_index: int


class IdeaReviseRequest(BaseModel):
    comment: str


class ProposalReviseRequest(BaseModel):
    feedback: str = ""


class ScoreRequest(BaseModel):
    version: Optional[int] = None
