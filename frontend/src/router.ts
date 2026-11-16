import { createRouter, createWebHistory } from "vue-router";
import { isAuthenticated } from "./auth";

const ai = { ai: true };

const routes = [
  { path: "/login", name: "login", meta: { title: "Anmelden" }, component: () => import("./views/LoginView.vue") },
  { path: "/", name: "dashboard", meta: { title: "Übersicht" }, component: () => import("./views/DashboardView.vue") },
  { path: "/import", name: "import", meta: { title: "Importieren" }, component: () => import("./views/ImportView.vue") },
  { path: "/bank", name: "bank", meta: { title: "Fragenbank" }, component: () => import("./views/BankView.vue") },
  { path: "/pruefung", name: "analysis", meta: { title: "Qualität" }, component: () => import("./views/AnalysisView.vue") },
  { path: "/planer", name: "planner", meta: { title: "Testplaner" }, component: () => import("./views/PlannerView.vue") },
  { path: "/verlauf", name: "history", meta: { title: "Verlauf" }, component: () => import("./views/HistoryView.vue") },
  // Optional AI generator: lecture material -> new questions.
  { path: "/ki", redirect: { name: "upload" } },
  { path: "/upload", name: "upload", meta: { ...ai, title: "KI-Generator: Material" }, component: () => import("./views/UploadView.vue") },
  { path: "/generate", name: "generate", meta: { ...ai, title: "KI-Generator: Fragen erzeugen" }, component: () => import("./views/GenerateView.vue") },
  { path: "/review", name: "review", meta: { ...ai, title: "KI-Generator: Prüfen" }, component: () => import("./views/ReviewView.vue") },
  { path: "/:pathMatch(.*)*", redirect: { name: "dashboard" } },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});

// Frontend guard for convenience ONLY. Real authorization is enforced by the
// backend on every request; this just keeps the UI tidy.
router.afterEach((to) => {
  const title = (to.meta.title as string | undefined) ?? "Moodle-Fragenbank";
  document.title = title === "Moodle-Fragenbank" ? title : `${title} · Moodle-Fragenbank`;
});

router.beforeEach((to) => {
  if (to.name !== "login" && !isAuthenticated()) return { name: "login" };
  if (to.name === "login" && isAuthenticated()) return { name: "dashboard" };
  return true;
});
