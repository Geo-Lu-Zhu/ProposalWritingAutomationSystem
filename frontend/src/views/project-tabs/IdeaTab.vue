<script setup>
import { computed, inject, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "../../api";

const props = defineProps({ id: String });
const router = useRouter();
const project = inject("project");
const refreshProject = inject("refreshProject");

const data = ref({ candidates: {}, rounds: [], selected: null });
const loading = ref(true);
const generating = ref(false);
const acting = ref(false);
const comment = ref("");
const error = ref("");

const candidates = computed(() => data.value.candidates?.candidates || []);
const recommendation = computed(() => data.value.candidates?.recommendation || null);
const rounds = computed(() => data.value.rounds || []);
const currentIdea = computed(() => rounds.value.length ? rounds.value[rounds.value.length - 1].idea_text : null);
const confirmed = computed(() => !!data.value.selected);

async function load() {
  loading.value = true;
  try {
    data.value = await api.getIdeas(props.id);
  } finally {
    loading.value = false;
  }
}

async function generate() {
  generating.value = true;
  error.value = "";
  try {
    await api.generateIdeas(props.id);
    await load();
  } catch (e) {
    error.value = e.message;
  } finally {
    generating.value = false;
  }
}

async function select(idx) {
  acting.value = true;
  error.value = "";
  try {
    await api.selectIdea(props.id, idx);
    await load();
  } catch (e) {
    error.value = e.message;
  } finally {
    acting.value = false;
  }
}

async function revise() {
  if (!comment.value.trim()) return;
  acting.value = true;
  error.value = "";
  try {
    await api.reviseIdea(props.id, comment.value.trim());
    comment.value = "";
    await load();
  } catch (e) {
    error.value = e.message;
  } finally {
    acting.value = false;
  }
}

async function confirm() {
  acting.value = true;
  error.value = "";
  try {
    await api.confirmIdea(props.id);
    await load();
    await refreshProject();
    router.push(`/projects/${props.id}/drafting`);
  } catch (e) {
    error.value = e.message;
  } finally {
    acting.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div v-if="loading" class="hint"><span class="spinner"></span> Loading…</div>
  <template v-else>
    <p v-if="error" class="error-box">{{ error }}</p>

    <div class="card" v-if="candidates.length === 0">
      <h2>Generate research idea candidates</h2>
      <p class="hint">Mistral will generate 10 candidate ideas grounded in your NOFO requirements; GPT-4o will recommend one.</p>
      <button @click="generate" :disabled="generating">
        <span v-if="generating" class="spinner"></span> Generate Ideas
      </button>
    </div>

    <div class="card" v-if="candidates.length && rounds.length === 0">
      <h2>Choose one idea to pursue</h2>
      <p class="hint" v-if="recommendation">Recommended: Idea {{ recommendation.recommended_index + 1 }} — {{ recommendation.reason }}</p>
      <div v-for="c in candidates" :key="c.index" class="list-item">
        <div class="row-between">
          <strong>Idea {{ c.index + 1 }}: {{ c.title }}</strong>
          <span v-if="recommendation && c.index === recommendation.recommended_index" class="badge badge-accent">Recommended</span>
        </div>
        <p class="hint">{{ c.rationale }}</p>
        <p class="hint"><strong>Methods:</strong> {{ c.methods }}</p>
        <p class="hint"><strong>Impact:</strong> {{ c.impact }}</p>
        <button @click="select(c.index)" :disabled="acting">Select this idea</button>
      </div>
    </div>

    <div class="card" v-if="currentIdea && !confirmed">
      <h2>Refine the selected idea</h2>
      <div class="list-item">
        <strong>{{ currentIdea.title }}</strong>
        <p class="hint">{{ currentIdea.rationale }}</p>
        <p class="hint"><strong>Methods:</strong> {{ currentIdea.methods }}</p>
        <p class="hint"><strong>Impact:</strong> {{ currentIdea.impact }}</p>
      </div>

      <div class="field">
        <label>Feedback (optional — revise before confirming)</label>
        <textarea v-model="comment" placeholder="e.g. make the timeline more feasible, tie it closer to requirement X"></textarea>
      </div>
      <div class="row">
        <button class="secondary" @click="revise" :disabled="acting || !comment.trim()">Revise idea</button>
        <button @click="confirm" :disabled="acting">Confirm & Start Drafting</button>
      </div>

      <details style="margin-top: 14px" v-if="rounds.length > 1">
        <summary class="hint">Revision history ({{ rounds.length }} rounds)</summary>
        <div v-for="(r, i) in rounds" :key="i" class="list-item">
          <div class="hint" v-if="r.comment"><em>Feedback:</em> {{ r.comment }}</div>
          <strong>{{ r.idea_text.title }}</strong>
          <p class="hint">{{ r.idea_text.rationale }}</p>
        </div>
      </details>
    </div>

    <div class="card" v-if="confirmed">
      <h2>Idea locked in</h2>
      <strong>{{ data.selected.idea.title }}</strong>
      <p class="hint">{{ data.selected.idea.rationale }}</p>
      <router-link :to="`/projects/${id}/drafting`"><button>Go to Drafting</button></router-link>
    </div>
  </template>
</template>
