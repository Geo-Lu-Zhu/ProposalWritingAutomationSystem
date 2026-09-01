import { createRouter, createWebHistory } from "vue-router";

import LibraryReferenceBank from "./views/LibraryReferenceBank.vue";
import LibraryTemplates from "./views/LibraryTemplates.vue";
import ProjectNew from "./views/ProjectNew.vue";
import ProjectsList from "./views/ProjectsList.vue";
import ProjectWorkspace from "./views/ProjectWorkspace.vue";
import ProjectSetupTab from "./views/project-tabs/SetupTab.vue";
import ProjectIdeaTab from "./views/project-tabs/IdeaTab.vue";
import ProjectDraftingTab from "./views/project-tabs/DraftingTab.vue";
import ProjectProposalTab from "./views/project-tabs/ProposalTab.vue";

const routes = [
  { path: "/", redirect: "/projects" },
  { path: "/library/reference-bank", component: LibraryReferenceBank },
  { path: "/library/templates", component: LibraryTemplates },
  { path: "/projects", component: ProjectsList },
  { path: "/projects/new", component: ProjectNew },
  {
    path: "/projects/:id",
    component: ProjectWorkspace,
    props: true,
    children: [
      { path: "", redirect: (to) => `/projects/${to.params.id}/setup` },
      { path: "setup", component: ProjectSetupTab, props: true },
      { path: "idea", component: ProjectIdeaTab, props: true },
      { path: "drafting", component: ProjectDraftingTab, props: true },
      { path: "proposal", component: ProjectProposalTab, props: true },
    ],
  },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});
