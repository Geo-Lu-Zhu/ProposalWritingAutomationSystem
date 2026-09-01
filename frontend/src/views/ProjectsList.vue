<script setup>
import { computed, onMounted, ref } from "vue";
import { api } from "../api";
import { refreshActiveProject } from "../composables/activeProject";

const projects = ref([]);

const active = computed(() => projects.value.filter((p) => p.status === "active"));
const archived = computed(() => projects.value.filter((p) => p.status === "archived"));

async function load() {
  projects.value = await api.listProjects();
}

async function archive(id) {
  await api.archiveProject(id);
  await load();
  await refreshActiveProject();
}

async function reopen(id) {
  await api.reopenProject(id);
  await load();
  await refreshActiveProject();
}

function formatDate(iso) {
  return new Date(iso).toLocaleString();
}

onMounted(load);
</script>

<template>
  <div class="row-between">
    <h1>Projects</h1>
    <router-link to="/projects/new"><button>New Project</button></router-link>
  </div>
  <p class="page-subtitle">Only one project is active at a time. Starting a new one archives the current one automatically.</p>

  <div class="card">
    <h2>Active</h2>
    <div v-if="active.length === 0" class="hint">No active project.</div>
    <div v-for="p in active" :key="p.id" class="list-item row-between">
      <div>
        <router-link :to="`/projects/${p.id}`"><strong>{{ p.name }}</strong></router-link>
        <div class="hint">Stage: {{ p.current_stage }} · created {{ formatDate(p.created_at) }}</div>
      </div>
      <button class="secondary" @click="archive(p.id)">Archive</button>
    </div>
  </div>

  <div class="card" v-if="archived.length">
    <h2>Archived</h2>
    <div v-for="p in archived" :key="p.id" class="list-item row-between">
      <div>
        <router-link :to="`/projects/${p.id}`"><strong>{{ p.name }}</strong></router-link>
        <div class="hint">Stage: {{ p.current_stage }} · created {{ formatDate(p.created_at) }}</div>
      </div>
      <button class="secondary" @click="reopen(p.id)">Reopen</button>
    </div>
  </div>
</template>
