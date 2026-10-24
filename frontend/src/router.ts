import { createRouter, createWebHistory } from "vue-router";
import { isAuthenticated } from "./auth";

const ai = { ai: true };

const routes = [
  { path: "/login", name: "login", component: () => import("./views/LoginView.vue") },
  { path: "/", name: "dashboard", component: () => import("./views/DashboardView.vue") },
  { path: "/import", name: "import", component: () => import("./views/ImportView.vue") },
  { path: "/bank", name: "bank", component: () => import("./views/BankView.vue") },
  { path: "/pruefung", name: "analysis", component: () => import("./views/AnalysisView.vue") },
  { path: "/verlauf", name: "history", component: () => import("./views/HistoryView.vue") },
  // Optional AI generator: lecture material -> new questions.
  { path: "/ki", redirect: { name: "upload" } },
  { path: "/upload", name: "upload", component: () => import("./views/UploadView.vue"), meta: ai },
  { path: "/generate", name: "generate", component: () => import("./views/GenerateView.vue"), meta: ai },
  { path: "/review", name: "review", component: () => import("./views/ReviewView.vue"), meta: ai },
  { path: "/:pathMatch(.*)*", redirect: { name: "dashboard" } },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});

// Frontend guard for convenience ONLY. Real authorization is enforced by the
// backend on every request; this just keeps the UI tidy.
router.beforeEach((to) => {
  if (to.name !== "login" && !isAuthenticated()) return { name: "login" };
  if (to.name === "login" && isAuthenticated()) return { name: "dashboard" };
  return true;
});
