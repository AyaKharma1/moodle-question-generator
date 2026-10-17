<script setup lang="ts">
import { useRouter } from "vue-router";
import { authState, logout } from "./auth";

const router = useRouter();

function onLogout() {
  logout();
  router.push({ name: "login" });
}
</script>

<template>
  <div class="app-shell">
    <header class="topbar" v-if="authState.user">
      <span class="brand">Moodle Fragen-Generator</span>
      <nav>
        <router-link to="/">Dashboard</router-link>
        <router-link to="/upload">Upload</router-link>
        <router-link to="/generate">Generieren</router-link>
        <router-link to="/review">Prüfen</router-link>
        <router-link to="/export">Export</router-link>
      </nav>
      <span class="spacer" />
      <span class="muted" style="color: #fff">{{ authState.user.email }}</span>
      <button class="secondary small" @click="onLogout">Abmelden</button>
    </header>
    <main class="content">
      <router-view />
    </main>
  </div>
</template>
