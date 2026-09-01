"""NOFO requirement topics + section outline templates.

Library-level files are the shared defaults. Each project gets its own
copy (written at project-creation time) that the user can edit freely
without affecting the shared default or other projects.
"""
from pathlib import Path

from app.storage import library_template_path, project_template_path, read_json, write_json

DEFAULT_NOFO_TOPICS: list[str] = [
    "Significance review criteria",
    "Innovation review criteria",
    "Approach review criteria",
    "responsiveness criteria",
    "must include",
    "prohibited activities",
    "data sharing requirements",
    "evaluation plan",
    "study design requirements",
    "digital health requirements",
    "behavioral health",
]

DEFAULT_SECTION_OUTLINE: list[dict] = [
    {
        "name": "Specific Aims",
        "query": "write specific aims for this NIH proposal",
        "nofo_topics": ["Significance review criteria"],
        "word_limit": 550,
    },
    {
        "name": "Significance",
        "query": "draft the Significance section of this NIH proposal",
        "nofo_topics": ["Significance review criteria"],
        "word_limit": 2000,
    },
    {
        "name": "Innovation",
        "query": "draft the Innovation section",
        "nofo_topics": ["Innovation review criteria"],
        "word_limit": 1200,
    },
    {
        "name": "Approach",
        "query": "draft the NIH Approach section",
        "nofo_topics": ["Approach review criteria"],
        "word_limit": 3400,
    },
]


def _default_for(name: str) -> list:
    return DEFAULT_NOFO_TOPICS if name == "nofo_topics" else DEFAULT_SECTION_OUTLINE


def get_library_template(name: str) -> list:
    path = library_template_path(name)
    return read_json(path, default=None) or _seed_library_template(name)


def _seed_library_template(name: str) -> list:
    data = _default_for(name)
    write_json(library_template_path(name), data)
    return data


def set_library_template(name: str, data: list) -> list:
    write_json(library_template_path(name), data)
    return data


def get_project_template(project_id: str, name: str) -> list:
    path = project_template_path(project_id, name)
    return read_json(path, default=None) or []


def set_project_template(project_id: str, name: str, data: list) -> list:
    write_json(project_template_path(project_id, name), data)
    return data


def seed_project_templates(project_id: str, nofo_topics: list | None, section_outline: list | None) -> None:
    """Copy either user-supplied overrides or the current library defaults into a new project."""
    set_project_template(project_id, "nofo_topics", nofo_topics if nofo_topics is not None else get_library_template("nofo_topics"))
    set_project_template(project_id, "section_outline", section_outline if section_outline is not None else get_library_template("section_outline"))
