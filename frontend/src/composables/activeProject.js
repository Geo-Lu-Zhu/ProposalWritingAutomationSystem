import { ref } from "vue";
import { api } from "../api";

// Module-level singleton so any component can trigger a refresh (e.g. after
// creating/archiving/reopening a project) and have the nav strip update.
export const activeProject = ref(null);

export async function refreshActiveProject() {
  const projects = await api.listProjects();
  activeProject.value = projects.find((p) => p.status === "active") || null;
}
