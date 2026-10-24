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
      <router-link to="/" class="brand"><span class="logo">MF</span> Moodle-Fragenbank</router-link>
      <nav>
        <router-link to="/">Übersicht</router-link>
        <router-link to="/import">Importieren</router-link>
        <router-link to="/bank">Fragenbank</router-link>
        <router-link to="/pruefung">Prüfung</router-link>
        <router-link to="/verlauf">Verlauf</router-link>
        <span class="sep" />
        <router-link to="/ki" :class="{ 'router-link-active': $route.meta.ai }">KI-Generator</router-link>
      </nav>
      <span class="spacer" />
      <span class="user">{{ authState.user.email }}</span>
      <button class="secondary small" @click="onLogout">Abmelden</button>
    </header>
    <main class="content">
      <router-view />
    </main>
  </div>
</template>
