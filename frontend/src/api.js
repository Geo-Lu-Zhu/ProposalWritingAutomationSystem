const API_BASE = "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(`${res.status} ${detail}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

function jsonBody(data) {
  return { headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) };
}

export const api = {
  // Library
  searchAuthors: (q) => request(`/library/authors/search?q=${encodeURIComponent(q)}`),
  listAuthors: () => request("/library/authors"),
  addAuthors: (authors) => request("/library/authors", { method: "POST", ...jsonBody({ authors }) }),

  uploadPapers: (files) => {
    const form = new FormData();
    for (const f of files) form.append("files", f);
    return request("/library/papers", { method: "POST", body: form });
  },
  listPapers: () => request("/library/papers"),
  listUnmatchedPapers: () => request("/library/papers/unmatched"),
  updatePaperCitation: (paperId, updates) =>
    request(`/library/papers/${paperId}/citation`, { method: "PATCH", ...jsonBody(updates) }),

  getLibraryTemplate: (name) => request(`/library/templates/${name}`),
  setLibraryTemplate: (name, data) => request(`/library/templates/${name}`, { method: "PUT", ...jsonBody({ data }) }),

  // Jobs
  getJob: (jobId) => request(`/jobs/${jobId}`),

  // Projects
  listProjects: () => request("/projects"),
  getProject: (id) => request(`/projects/${id}`),
  createProject: ({ name, nofoFile, nofoTopics, sectionOutline }) => {
    const form = new FormData();
    form.append("name", name || "");
    form.append("nofo_file", nofoFile);
    if (nofoTopics) form.append("nofo_topics", JSON.stringify(nofoTopics));
    if (sectionOutline) form.append("section_outline", JSON.stringify(sectionOutline));
    return request("/projects", { method: "POST", body: form });
  },
  archiveProject: (id) => request(`/projects/${id}/archive`, { method: "POST" }),
  reopenProject: (id) => request(`/projects/${id}/reopen`, { method: "POST" }),

  getProjectTemplate: (id, name) => request(`/projects/${id}/templates/${name}`),
  setProjectTemplate: (id, name, data) =>
    request(`/projects/${id}/templates/${name}`, { method: "PUT", ...jsonBody({ data }) }),

  getNofoRequirements: (id) => request(`/projects/${id}/nofo/requirements`),

  generateIdeas: (id) => request(`/projects/${id}/ideas/generate`, { method: "POST" }),
  getIdeas: (id) => request(`/projects/${id}/ideas`),
  selectIdea: (id, candidateIndex) =>
    request(`/projects/${id}/ideas/select`, { method: "POST", ...jsonBody({ candidate_index: candidateIndex }) }),
  reviseIdea: (id, comment) =>
    request(`/projects/${id}/ideas/revise`, { method: "POST", ...jsonBody({ comment }) }),
  confirmIdea: (id) => request(`/projects/${id}/ideas/confirm`, { method: "POST" }),

  startDrafting: (id) => request(`/projects/${id}/draft/start`, { method: "POST" }),
  getSectionDrafts: (id) => request(`/projects/${id}/draft/sections`),
  getProposal: (id) => request(`/projects/${id}/proposal`),
  listProposalVersions: (id) => request(`/projects/${id}/proposal/versions`),
  getProposalVersion: (id, version) => request(`/projects/${id}/proposal/versions/${version}`),
  reviseProposal: (id, feedback) =>
    request(`/projects/${id}/proposal/revise`, { method: "POST", ...jsonBody({ feedback }) }),
  scoreProposal: (id, version = null) =>
    request(`/projects/${id}/proposal/score`, { method: "POST", ...jsonBody({ version }) }),
};
