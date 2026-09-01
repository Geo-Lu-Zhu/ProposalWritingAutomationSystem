<script setup>
import { onMounted, ref } from "vue";
import { api } from "../api";

const topics = ref([]);
const newTopic = ref("");
const topicsSaving = ref(false);
const topicsSaved = ref(false);

const outline = ref([]);
const outlineSaving = ref(false);
const outlineSaved = ref(false);

async function load() {
  topics.value = await api.getLibraryTemplate("nofo-topics");
  outline.value = await api.getLibraryTemplate("section-outline");
}

function addTopic() {
  const t = newTopic.value.trim();
  if (!t || topics.value.includes(t)) return;
  topics.value.push(t);
  newTopic.value = "";
}

function removeTopic(t) {
  topics.value = topics.value.filter((x) => x !== t);
  for (const s of outline.value) {
    s.nofo_topics = s.nofo_topics.filter((x) => x !== t);
  }
}

async function saveTopics() {
  topicsSaving.value = true;
  try {
    await api.setLibraryTemplate("nofo-topics", topics.value);
    topicsSaved.value = true;
    setTimeout(() => (topicsSaved.value = false), 1500);
  } finally {
    topicsSaving.value = false;
  }
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

async function saveOutline() {
  outlineSaving.value = true;
  try {
    await api.setLibraryTemplate("section-outline", outline.value);
    outlineSaved.value = true;
    setTimeout(() => (outlineSaved.value = false), 1500);
  } finally {
    outlineSaving.value = false;
  }
}

onMounted(load);
</script>

<template>
  <h1>Templates</h1>
  <p class="page-subtitle">
    Shared defaults used when a new project is created. Each project gets its own editable copy at
    creation time, so changes here only affect future projects, not existing ones.
  </p>

  <div class="card">
    <h2>NOFO requirement topics</h2>
    <p class="hint">Categories the app extracts structured requirements for from any NOFO you upload.</p>

    <div v-for="t in topics" :key="t" class="row" style="margin-top: 8px">
      <input type="text" :value="t" disabled style="flex: 1" />
      <button class="danger" @click="removeTopic(t)">Remove</button>
    </div>

    <div class="row" style="margin-top: 12px">
      <input type="text" v-model="newTopic" placeholder="New topic" @keyup.enter="addTopic" />
      <button class="secondary" @click="addTopic">Add</button>
    </div>

    <div class="row" style="margin-top: 14px">
      <button @click="saveTopics" :disabled="topicsSaving">Save topics</button>
      <span v-if="topicsSaved" class="hint">Saved.</span>
    </div>
  </div>

  <div class="card">
    <h2>Section outline</h2>
    <p class="hint">The proposal sections generated, in order, each with its drafting query, linked NOFO topics, and word limit.</p>

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

    <div class="row" style="margin-top: 14px">
      <button class="secondary" @click="addSection">Add section</button>
      <button @click="saveOutline" :disabled="outlineSaving">Save outline</button>
      <span v-if="outlineSaved" class="hint">Saved.</span>
    </div>
  </div>
</template>
