<script setup>
import { computed, inject, onBeforeUnmount, onMounted, ref } from "vue";
import { api } from "../../api";
import { useJobPolling } from "../../composables/useJobPolling";

const props = defineProps({ id: String });
const project = inject("project");
const refreshProject = inject("refreshProject");

const sections = ref([]);
const loading = ref(true);
const starting = ref(false);
const error = ref("");
const job = useJobPolling();

let resumeTimer = null;

const notReady = computed(() => project.value?.current_stage === "idea" || project.value?.current_stage === "setup");
const hasAnyDraft = computed(() => sections.value.some((s) => s.first_draft));
const inProgress = computed(() => project.value?.current_stage === "drafting" && job.status.value !== "done");

async function loadSections() {
  sections.value = await api.getSectionDrafts(props.id);
  loading.value = false;
}

async function start() {
  starting.value = true;
  error.value = "";
  try {
    const { job_id } = await api.startDrafting(props.id);
    job.watchJob(job_id);
    watchResult();
  } catch (e) {
    error.value = e.message;
    starting.value = false;
  }
}

function watchResult() {
  const check = setInterval(async () => {
    await loadSections();
    if (job.status.value === "done") {
      clearInterval(check);
      await refreshProject();
    } else if (job.status.value === "error") {
      clearInterval(check);
      error.value = job.error.value;
    }
  }, 2000);
}

// Resilience for page reloads mid-job: no job_id survives a refresh, so
// silently poll section drafts + project stage until drafting completes.
function startResumePolling() {
  resumeTimer = setInterval(async () => {
    await loadSections();
    await refreshProject();
    if (project.value?.current_stage !== "drafting") {
      clearInterval(resumeTimer);
    }
  }, 3000);
}

onMounted(async () => {
  await loadSections();
  if (project.value?.current_stage === "drafting" && job.status.value === null) {
    startResumePolling();
  }
});
onBeforeUnmount(() => resumeTimer && clearInterval(resumeTimer));
</script>

<template>
  <div v-if="notReady" class="card hint">Confirm a research idea first before drafting can begin.</div>

  <template v-else>
    <p v-if="error" class="error-box">{{ error }}</p>

    <div class="card" v-if="!hasAnyDraft && project.current_stage === 'drafting' && job.status.value !== 'running' && job.status.value !== 'queued'">
      <h2>Draft the proposal</h2>
      <p class="hint">Runs unattended through each section: retrieve evidence → draft → NIH-style review → revise.</p>
      <button @click="start" :disabled="starting">Start Drafting</button>
    </div>

    <div class="card" v-if="job.status.value === 'running' || job.status.value === 'queued'">
      <div class="hint">
        <span class="spinner"></span>
        <template v-if="job.progress.value.section">
          {{ job.progress.value.step }} — {{ job.progress.value.section }} ({{ job.progress.value.section_index }}/{{ job.progress.value.section_count }})
        </template>
        <template v-else>{{ job.progress.value.step || "Starting…" }}</template>
      </div>
    </div>

    <div class="card" v-if="inProgress && job.status.value === null">
      <div class="hint"><span class="spinner"></span> Drafting in progress (resumed after reload)…</div>
    </div>

    <div class="card" v-if="project.current_stage === 'proposal'">
      <router-link :to="`/projects/${id}/proposal`"><button>View Proposal</button></router-link>
    </div>

    <div class="card" v-if="sections.length">
      <h2>Sections</h2>
      <details v-for="s in sections" :key="s.name" class="list-item" :open="!!s.revised_draft">
        <summary><strong>{{ s.name }}</strong> <span v-if="!s.first_draft" class="hint">— pending</span></summary>
        <div v-if="s.first_draft">
          <h3 class="hint">First draft</h3>
          <div class="section-text">{{ s.first_draft }}</div>
          <h3 class="hint" v-if="s.reviewer_feedback">Reviewer feedback</h3>
          <div v-if="s.reviewer_feedback" class="section-text">
            Significance: {{ s.reviewer_feedback.score_significance }} · Innovation: {{ s.reviewer_feedback.score_innovation }} · Approach: {{ s.reviewer_feedback.score_approach }}
            <p><strong>Strengths:</strong> {{ s.reviewer_feedback.strengths }}</p>
            <p><strong>Weaknesses:</strong> {{ s.reviewer_feedback.weaknesses }}</p>
          </div>
          <h3 class="hint" v-if="s.revised_draft">Revised draft</h3>
          <div v-if="s.revised_draft" class="section-text">{{ s.revised_draft }}</div>
        </div>
      </details>
    </div>
  </template>
</template>
