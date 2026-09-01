<script setup>
import { computed, inject, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { api } from "../../api";

const props = defineProps({ id: String });
const project = inject("project");
const refreshProject = inject("refreshProject");

const requirements = ref({});
const loading = ref(true);
let timer = null;

const topics = computed(() => Object.keys(requirements.value));
const ingesting = computed(() => project.value?.current_stage === "setup" && topics.value.length === 0);

async function poll() {
  requirements.value = await api.getNofoRequirements(props.id);
  loading.value = false;
  if (Object.keys(requirements.value).length === 0) {
    timer = setTimeout(poll, 2000);
  } else if (project.value?.current_stage === "setup") {
    await refreshProject();
  }
}

onMounted(poll);
onBeforeUnmount(() => timer && clearTimeout(timer));
</script>

<template>
  <div v-if="loading" class="hint"><span class="spinner"></span> Loading…</div>
  <template v-else>
    <div class="card" v-if="ingesting">
      <div class="hint"><span class="spinner"></span> Ingesting NOFO and extracting requirements — this can take a minute or two.</div>
    </div>

    <div class="card" v-if="topics.length">
      <div class="row-between">
        <h2>NOFO requirements extracted</h2>
        <router-link :to="`/projects/${id}/idea`"><button>Continue to Idea Generation</button></router-link>
      </div>
      <div v-for="t in topics" :key="t" class="list-item">
        <strong>{{ t }}</strong>
        <ul v-if="requirements[t]?.requirements?.length">
          <li v-for="(r, i) in requirements[t].requirements" :key="i">{{ r }}</li>
        </ul>
        <p v-else class="hint">No structured requirements extracted for this topic.</p>
      </div>
    </div>
  </template>
</template>
