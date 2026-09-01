<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "../api";
import { refreshActiveProject } from "../composables/activeProject";

const router = useRouter();

const name = ref("");
const nofoFile = ref(null);
const topics = ref([]);
const newTopic = ref("");
const outline = ref([]);
const submitting = ref(false);
const error = ref("");

function onFileChange(e) {
  nofoFile.value = e.target.files[0] || null;
}

function addTopic() {
  const t = newTopic.value.trim();
  if (!t || topics.value.includes(t)) return;
  topics.value.push(t);
  newTopic.value = "";
}

function removeTopic(t) {
  topics.value = topics.value.filter((x) => x !== t);
  for (const s of outline.value) s.nofo_topics = s.nofo_topics.filter((x) => x !== t);
}

function addSection() {
  outline.value.push({ name: "New Section", query: "", nofo_topics: [], word_limit: null });
}

function removeSection(i) {
  outline.value.splice(i, 1);
}

function toggleTopic(section, topic) {
  const i = section.nofo_topics.indexOf(topic);
  if (i === -1) section.nofo_topics.push(topic);
  else section.nofo_topics.splice(i, 1);
}

async function submit() {
  error.value = "";
  if (!nofoFile.value) {
    error.value = "Upload a NOFO PDF first.";
    return;
  }
  submitting.value = true;
  try {
    const { project } = await api.createProject({
      name: name.value,
      nofoFile: nofoFile.value,
      nofoTopics: topics.value,
      sectionOutline: outline.value,
    });
    await refreshActiveProject();
    router.push(`/projects/${project.id}/setup`);
  } catch (e) {
    error.value = e.message;
    submitting.value = false;
  }
}

onMounted(async () => {
  topics.value = await api.getLibraryTemplate("nofo-topics");
  outline.value = await api.getLibraryTemplate("section-outline");
});
</script>

<template>
  <h1>New Project</h1>
  <p class="page-subtitle">
    Starting this project will archive whatever project is currently active. Topics and section
    outline below start as your shared library defaults — edit them here without affecting the
    shared defaults or any other project.
  </p>

  <p v-if="error" class="error-box">{{ error }}</p>

  <div class="card">
    <div class="field">
      <label>Project name</label>
      <input type="text" v-model="name" placeholder="e.g. PAR-25-136 Digital Health R01" />
    </div>
    <div class="field">
      <label>NOFO document</label>
      <p class="hint">
        Upload the funding announcement / solicitation (NOFO) PDF you're responding to — this is
        the funding opportunity, not one of your own papers.
      </p>
      <input type="file" accept="application/pdf" @change="onFileChange" />
    </div>
  </div>

  <div class="card">
    <h2>NOFO requirement topics (this project)</h2>
    <div v-for="t in topics" :key="t" class="row" style="margin-top: 8px">
      <input type="text" :value="t" disabled style="flex: 1" />
      <button class="danger" @click="removeTopic(t)">Remove</button>
    </div>
    <div class="row" style="margin-top: 12px">
      <input type="text" v-model="newTopic" placeholder="New topic" @keyup.enter="addTopic" />
      <button class="secondary" @click="addTopic">Add</button>
    </div>
  </div>

  <div class="card">
    <h2>Section outline (this project)</h2>
    <div v-for="(s, i) in outline" :key="i" class="list-item">
      <div class="field"><label>Section name</label><input type="text" v-model="s.name" /></div>
      <div class="field"><label>Generation query</label><textarea v-model="s.query"></textarea></div>
      <div class="field">
        <label>Word limit</label>
        <input type="text" v-model.number="s.word_limit" style="max-width: 120px" />
      </div>
      <div class="field">
        <label>Linked NOFO topics</label>
        <div class="row" style="flex-wrap: wrap; gap: 6px">
          <span
            v-for="t in topics"
            :key="t"
            class="badge"
            :class="s.nofo_topics.includes(t) ? 'badge-accent' : 'badge-muted'"
            style="cursor: pointer"
            @click="toggleTopic(s, t)"
          >
            {{ t }}
          </span>
        </div>
      </div>
      <button class="danger" @click="removeSection(i)">Remove section</button>
    </div>
    <button class="secondary" @click="addSection">Add section</button>
  </div>

  <button @click="submit" :disabled="submitting">
    <span v-if="submitting" class="spinner"></span>
    Create Project & Start Ingestion
  </button>
</template>
