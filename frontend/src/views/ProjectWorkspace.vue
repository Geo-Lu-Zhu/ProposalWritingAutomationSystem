<script setup>
import { computed, onMounted, provide, ref, watch } from "vue";
import { api } from "../api";

const props = defineProps({ id: String });

const project = ref(null);
const error = ref("");

async function refreshProject() {
  try {
    project.value = await api.getProject(props.id);
  } catch (e) {
    error.value = e.message;
  }
}

provide("project", project);
provide("refreshProject", refreshProject);

const stageOrder = ["setup", "idea", "drafting", "proposal"];
const currentStageIndex = computed(() => stageOrder.indexOf(project.value?.current_stage || "setup"));

function tabReachable(tab) {
  return stageOrder.indexOf(tab) <= currentStageIndex.value;
}

watch(() => props.id, refreshProject, { immediate: true });
onMounted(refreshProject);
</script>

<template>
  <p v-if="error" class="error-box">{{ error }}</p>
  <template v-if="project">
    <div class="row-between">
      <h1>{{ project.name }}</h1>
      <span class="badge" :class="project.status === 'active' ? 'badge-success' : 'badge-muted'">{{ project.status }}</span>
    </div>

    <nav class="tabs">
      <router-link :to="`/projects/${id}/setup`">Setup</router-link>
      <router-link :to="`/projects/${id}/idea`" :class="{ disabled: !tabReachable('idea') }">Idea</router-link>
      <router-link :to="`/projects/${id}/drafting`" :class="{ disabled: !tabReachable('drafting') }">Drafting</router-link>
      <router-link :to="`/projects/${id}/proposal`" :class="{ disabled: !tabReachable('proposal') }">Proposal</router-link>
    </nav>

    <router-view :project="project" @stage-changed="refreshProject" />
  </template>
</template>
