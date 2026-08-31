<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { api } from "../api";
import { useJobPolling } from "../composables/useJobPolling";

const authorQuery = ref("");
const searchResults = ref([]);
const searching = ref(false);
const searchError = ref("");

const savedAuthors = ref([]);
const papers = ref([]);

const fileInput = ref(null);
const uploadJob = useJobPolling();

const editingPaperId = ref(null);
const editForm = ref({ title: "", authors: "", year: "", venue: "", doi: "" });

const savedAuthorIds = computed(() => new Set(savedAuthors.value.map((a) => a.author_id)));

async function refreshAll() {
  savedAuthors.value = await api.listAuthors();
  papers.value = await api.listPapers();
}

async function runSearch() {
  if (!authorQuery.value.trim()) return;
  searching.value = true;
  searchError.value = "";
  try {
    searchResults.value = await api.searchAuthors(authorQuery.value.trim());
  } catch (e) {
    searchError.value = e.message;
  } finally {
    searching.value = false;
  }
}

async function addAuthor(candidate) {
  await api.addAuthors([{ author_id: candidate.author_id, name: candidate.name }]);
  await refreshAll();
}

async function uploadSelectedFiles() {
  const files = fileInput.value?.files;
  if (!files || files.length === 0) return;
  const { job_id } = await api.uploadPapers(Array.from(files));
  uploadJob.watchJob(job_id);
  fileInput.value.value = "";
}

// Refresh the papers list once the upload job finishes.
watch(uploadJob.status, (s) => {
  if (s === "done") refreshAll();
});

function startEdit(paper) {
  editingPaperId.value = paper.paper_id;
  editForm.value = {
    title: paper.title || "",
    authors: paper.authors || "",
    year: paper.year || "",
    venue: paper.venue || "",
    doi: paper.doi || "",
  };
}

function cancelEdit() {
  editingPaperId.value = null;
}

async function saveEdit(paperId) {
  await api.updatePaperCitation(paperId, editForm.value);
  editingPaperId.value = null;
  await refreshAll();
}

function statusBadgeClass(status) {
  if (status === "matched") return "badge-success";
  if (status === "manual") return "badge-accent";
  if (status === "unmatched") return "badge-warn";
  return "badge-muted";
}

onMounted(refreshAll);
</script>

<template>
  <h1>Reference Bank</h1>
  <p class="page-subtitle">
    Shared across all projects. This is the pool of your own prior publications used to ground
    research idea generation and to source cited evidence in drafted proposal sections.
  </p>

  <div class="card">
    <h2>Find yourself on Semantic Scholar</h2>
    <p class="hint">
      Search by name to find your Semantic Scholar author profile. If there are multiple people
      with your name, use their most-cited papers below to tell them apart, then add the correct
      one(s).
    </p>
    <div class="row" style="margin-top: 10px">
      <input type="search" v-model="authorQuery" placeholder="e.g. Jane Smith" @keyup.enter="runSearch" />
      <button @click="runSearch" :disabled="searching">Search</button>
    </div>
    <p v-if="searchError" class="error-box">{{ searchError }}</p>

    <div v-if="searchResults.length" style="margin-top: 14px">
      <div v-for="c in searchResults" :key="c.author_id" class="list-item">
        <div class="row-between">
          <div>
            <strong>{{ c.name }}</strong>
            <span class="hint" v-if="c.affiliations?.length"> — {{ c.affiliations.join(", ") }}</span>
            <div class="hint">{{ c.paper_count }} papers · {{ c.citation_count }} citations · h-index {{ c.h_index }}</div>
          </div>
          <button v-if="savedAuthorIds.has(c.author_id)" class="secondary" disabled>Added</button>
          <button v-else @click="addAuthor(c)">Add</button>
        </div>
        <ul v-if="c.top_papers?.length" class="hint" style="margin: 6px 0 0; padding-left: 18px">
          <li v-for="p in c.top_papers" :key="p.title">
            {{ p.title }} <template v-if="p.year">({{ p.year }})</template> — {{ p.citationCount }} citations
          </li>
        </ul>
      </div>
    </div>

    <div v-if="savedAuthors.length" style="margin-top: 14px">
      <strong>Saved authors:</strong>
      <span v-for="a in savedAuthors" :key="a.author_id" class="badge badge-accent" style="margin-left: 6px">
        {{ a.name }}
      </span>
    </div>
  </div>

  <div class="card">
    <h2>Upload your papers</h2>
    <p class="hint">
      Upload PDFs of <strong>your own</strong> prior publications — not other people's papers. This
      corpus represents your research expertise and is what the app uses to ground the ideas it
      proposes and the evidence it cites in the Approach section. Uploading unrelated papers will
      skew idea generation toward work that isn't yours.
    </p>
    <div class="row" style="margin-top: 10px">
      <input ref="fileInput" type="file" accept="application/pdf" multiple />
      <button @click="uploadSelectedFiles" :disabled="uploadJob.status.value === 'running'">Upload</button>
    </div>

    <div v-if="uploadJob.status.value && uploadJob.status.value !== 'done'" class="hint" style="margin-top: 10px">
      <span class="spinner"></span>
      <template v-if="uploadJob.progress.value.file">
        Ingesting {{ uploadJob.progress.value.file }} ({{ uploadJob.progress.value.file_index }}/{{ uploadJob.progress.value.file_count }})
      </template>
      <template v-else>Starting…</template>
    </div>
    <p v-if="uploadJob.error.value" class="error-box">{{ uploadJob.error.value }}</p>
  </div>

  <div class="card">
    <h2>Papers ({{ papers.length }})</h2>
    <table v-if="papers.length">
      <thead>
        <tr>
          <th>Title</th>
          <th>Authors</th>
          <th>Year</th>
          <th>Status</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <template v-for="p in papers" :key="p.paper_id">
          <tr>
            <td>{{ p.title }}</td>
            <td>{{ p.authors }}</td>
            <td>{{ p.year }}</td>
            <td><span class="badge" :class="statusBadgeClass(p.status)">{{ p.status }}</span></td>
            <td>
              <button class="secondary" @click="startEdit(p)" v-if="editingPaperId !== p.paper_id">Edit citation</button>
            </td>
          </tr>
          <tr v-if="editingPaperId === p.paper_id">
            <td colspan="5">
              <div class="field"><label>Title</label><input type="text" v-model="editForm.title" /></div>
              <div class="field"><label>Authors</label><input type="text" v-model="editForm.authors" /></div>
              <div class="row">
                <div class="field" style="flex: 1"><label>Year</label><input type="text" v-model="editForm.year" /></div>
                <div class="field" style="flex: 2"><label>Venue</label><input type="text" v-model="editForm.venue" /></div>
                <div class="field" style="flex: 2"><label>DOI</label><input type="text" v-model="editForm.doi" /></div>
              </div>
              <div class="row">
                <button @click="saveEdit(p.paper_id)">Save</button>
                <button class="secondary" @click="cancelEdit">Cancel</button>
              </div>
            </td>
          </tr>
        </template>
      </tbody>
    </table>
    <p v-else class="hint">No papers uploaded yet.</p>
  </div>
</template>
