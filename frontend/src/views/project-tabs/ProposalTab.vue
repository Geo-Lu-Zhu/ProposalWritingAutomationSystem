<script setup>
import { computed, onMounted, ref } from "vue";
import { api } from "../../api";

const props = defineProps({ id: String });

const proposal = ref(null);
const versions = ref([]);
const loading = ref(true);
const notDrafted = ref(false);
const feedback = ref("");
const revising = ref(false);
const scoring = ref(false);
const error = ref("");
const viewingVersion = ref(null);

const scoreIsStale = computed(() => {
  const s = proposal.value?.score;
  return s && proposal.value && s.version !== proposal.value.version;
});

async function load() {
  loading.value = true;
  error.value = "";
  try {
    proposal.value = await api.getProposal(props.id);
    versions.value = await api.listProposalVersions(props.id);
    notDrafted.value = false;
  } catch (e) {
    notDrafted.value = true;
  } finally {
    loading.value = false;
  }
}

async function revise() {
  revising.value = true;
  error.value = "";
  try {
    await api.reviseProposal(props.id, feedback.value);
    feedback.value = "";
    viewingVersion.value = null;
    await load();
  } catch (e) {
    error.value = e.message;
  } finally {
    revising.value = false;
  }
}

async function requestScore() {
  scoring.value = true;
  error.value = "";
  try {
    await api.scoreProposal(props.id);
    await load();
  } catch (e) {
    error.value = e.message;
  } finally {
    scoring.value = false;
  }
}

async function viewVersion(v) {
  viewingVersion.value = await api.getProposalVersion(props.id, v);
}

function backToCurrent() {
  viewingVersion.value = null;
}

onMounted(load);
</script>

<template>
  <div v-if="loading" class="hint"><span class="spinner"></span> Loading…</div>
  <div v-else-if="notDrafted" class="card hint">No proposal drafted yet — finish the Drafting step first.</div>

  <template v-else>
    <p v-if="error" class="error-box">{{ error }}</p>

    <div class="card" v-if="viewingVersion">
      <div class="row-between">
        <h2>Version {{ viewingVersion.version }} (historical)</h2>
        <button class="secondary" @click="backToCurrent">Back to current</button>
      </div>
      <div v-for="(text, name) in viewingVersion.sections" :key="name" class="list-item">
        <strong>{{ name }}</strong>
        <div class="section-text">{{ text }}</div>
      </div>
      <div class="list-item">
        <strong>References</strong>
        <div class="section-text">{{ viewingVersion.references }}</div>
      </div>
    </div>

    <template v-else>
      <div class="card">
        <div class="row-between">
          <h2>Proposal (version {{ proposal.version }})</h2>
          <span class="hint">{{ proposal.meta.created_from === "revision" ? "revised" : "auto-generated" }} · {{ new Date(proposal.meta.created_at).toLocaleString() }}</span>
        </div>
        <div v-for="(text, name) in proposal.sections" :key="name" class="list-item">
          <strong>{{ name }}</strong>
          <div class="section-text">{{ text }}</div>
        </div>
        <div class="list-item">
          <strong>References</strong>
          <div class="section-text">{{ proposal.references }}</div>
        </div>
      </div>

      <div class="card">
        <div class="row-between">
          <h2>NIH-style score</h2>
          <button class="secondary" @click="requestScore" :disabled="scoring">
            <span v-if="scoring" class="spinner"></span> Request Final Scoring
          </button>
        </div>
        <div v-if="!proposal.score" class="hint">Not yet scored.</div>
        <div v-else>
          <span v-if="scoreIsStale" class="badge badge-warn">From version {{ proposal.score.version }} — proposal has since changed</span>
          <p>
            Significance: {{ proposal.score.report.section_scores?.Significance }} ·
            Innovation: {{ proposal.score.report.section_scores?.Innovation }} ·
            Approach: {{ proposal.score.report.section_scores?.Approach }} ·
            Overall impact: {{ proposal.score.report.overall_impact }}
          </p>
          <p><strong>Strengths:</strong> {{ proposal.score.report.strengths }}</p>
          <p><strong>Weaknesses:</strong> {{ proposal.score.report.weaknesses }}</p>
          <p><strong>Summary:</strong> {{ proposal.score.report.summary_statement }}</p>
        </div>
      </div>

      <div class="card">
        <h2>Revise with feedback</h2>
        <p class="hint">Scoring does not re-run automatically after a revision — use the button above when you're ready.</p>
        <div class="field">
          <textarea v-model="feedback" placeholder="e.g. emphasize the core research idea more in Significance, tighten Approach to stay under the word limit"></textarea>
        </div>
        <button @click="revise" :disabled="revising || !feedback.trim()">
          <span v-if="revising" class="spinner"></span> Revise
        </button>
      </div>

      <div class="card" v-if="versions.length > 1">
        <h2>Version history</h2>
        <div v-for="v in [...versions].reverse()" :key="v.version" class="list-item row-between">
          <span>v{{ v.version }} — {{ v.created_from }} — {{ new Date(v.created_at).toLocaleString() }}</span>
          <button class="secondary" @click="viewVersion(v.version)">View</button>
        </div>
      </div>
    </template>
  </template>
</template>
