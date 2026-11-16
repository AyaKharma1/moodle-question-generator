import { createApp } from "vue";
import App from "./App.vue";
import { router } from "./router";
import { loadUser, logout } from "./auth";
import { onUnauthorized } from "./api";
import "./style.css";

onUnauthorized(() => {
  logout();
  router.push({ name: "login", query: { expired: "1" } });
});

// Restore the session (if any) before mounting, so guards see the right state.
loadUser().finally(() => {
  createApp(App).use(router).mount("#app");
});
