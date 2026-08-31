"""Global (per-project) numeric citation registry.

Ported from the notebook's ProposalState.citation_registry /
citation_metadata: every source that gets cited anywhere in the proposal
gets a single stable number, assigned in first-seen order, shared across
all sections so [3] means the same source everywhere.
"""
import re

from app.storage import project_dir, read_json, write_json

CITATION_ID_RE = re.compile(r"\[(\d+)\]")


def _path(project_id: str):
    return project_dir(project_id) / "citations.json"


class ProjectCitations:
    def __init__(self, project_id: str):
        self.project_id = project_id
        data = read_json(_path(project_id), default={"registry": {}, "metadata": {}})
        self.registry: dict[str, int] = data["registry"]
        self.metadata: dict[str, dict] = data["metadata"]

    def register(self, citation_id: str, metadata: dict | None = None) -> int:
        cid = str(citation_id)
        if cid not in self.registry:
            self.registry[cid] = len(self.registry) + 1
        if cid not in self.metadata:
            self.metadata[cid] = metadata or {
                "title": f"Unknown Source {cid}",
                "authors": "Unknown Authors",
                "year": "n.d.",
                "venue": "",
                "doi": "",
            }
        return self.registry[cid]

    def sync_from_text(self, text: str) -> None:
        """Guarantee every [n] literally present in generated text has metadata,
        even if it wasn't registered through the normal retrieval path."""
        num_to_cid = {num: cid for cid, num in self.registry.items()}
        for num_str in CITATION_ID_RE.findall(text):
            num = int(num_str)
            if num not in num_to_cid and str(num) not in self.metadata:
                # Unknown number the LLM introduced; register a placeholder under its own key.
                self.registry.setdefault(str(num), num)
                self.metadata.setdefault(str(num), {
                    "title": f"Reference {num}",
                    "authors": "Author et al.",
                    "year": "n.d.",
                    "venue": "",
                    "doi": "",
                })

    def citation_map_text(self) -> str:
        num_to_cid = {num: cid for cid, num in self.registry.items()}
        lines = []
        for num in sorted(num_to_cid.keys()):
            cid = num_to_cid[num]
            title = self.metadata.get(cid, {}).get("title", f"Unknown Source {cid}")
            lines.append(f"[{num}] {title}")
        return "\n".join(lines)

    def reference_list_text(self) -> str:
        num_to_cid = {num: cid for cid, num in self.registry.items()}
        lines = []
        for num in sorted(num_to_cid.keys()):
            cid = num_to_cid[num]
            meta = self.metadata.get(cid, {})
            parts = []
            if meta.get("authors"):
                parts.append(meta["authors"])
            if meta.get("year"):
                parts.append(f"({meta['year']})")
            if meta.get("title"):
                title = meta["title"]
                parts.append(title if title.endswith(".") else title + ".")
            if meta.get("venue"):
                venue = meta["venue"]
                parts.append(venue if venue.endswith(".") else venue + ".")
            if meta.get("doi"):
                parts.append(f"doi:{meta['doi']}")
            lines.append(f"[{num}] " + (" ".join(parts) if parts else "Reference information missing."))
        return "\n".join(lines)

    def save(self) -> None:
        write_json(_path(self.project_id), {"registry": self.registry, "metadata": self.metadata})
