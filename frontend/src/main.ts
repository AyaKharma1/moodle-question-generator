import { createApp } from "vue";
import App from "./App.vue";
import { router } from "./router";
import { loadUser } from "./auth";
import "./style.css";

// Restore the session (if any) before mounting, so guards see the right state.
loadUser().finally(() => {
  createApp(App).use(router).mount("#app");
});
