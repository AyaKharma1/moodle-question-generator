import { createRouter, createWebHistory } from "vue-router";
import { isAuthenticated } from "./auth";

const routes = [
  { path: "/login", name: "login", component: () => import("./views/LoginView.vue") },
  { path: "/", name: "dashboard", component: () => import("./views/DashboardView.vue") },
  { path: "/upload", name: "upload", component: () => import("./views/UploadView.vue") },
  { path: "/generate", name: "generate", component: () => import("./views/GenerateView.vue") },
  { path: "/review", name: "review", component: () => import("./views/ReviewView.vue") },
  { path: "/export", name: "export", component: () => import("./views/ExportView.vue") },
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
