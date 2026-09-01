<script setup>
import { onMounted } from "vue";
import { activeProject, refreshActiveProject } from "./composables/activeProject";

onMounted(refreshActiveProject);
</script>

<template>
  <div class="app-shell">
    <header class="topnav">
      <div class="topnav-brand">Proposal Writing Automation</div>
      <nav class="topnav-links">
        <router-link to="/projects">Projects</router-link>
        <router-link to="/library/reference-bank">Reference Bank</router-link>
        <router-link to="/library/templates">Templates</router-link>
      </nav>
      <div class="topnav-active">
        <template v-if="activeProject">
          Active:
          <router-link :to="`/projects/${activeProject.id}`">{{ activeProject.name }}</router-link>
        </template>
        <template v-else>No active project</template>
      </div>
    </header>
    <main class="app-main">
      <router-view />
    </main>
  </div>
</template>
