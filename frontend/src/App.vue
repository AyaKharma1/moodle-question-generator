<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { authState, logout } from "./auth";

const router = useRouter();
const quick = ref("");

function quickSearch() {
  router.push({ name: "bank", query: quick.value.trim() ? { q: quick.value.trim() } : {} });
  quick.value = "";
}

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
        <router-link to="/pruefung">Qualität</router-link>
        <router-link to="/planer">Testplaner</router-link>
        <router-link to="/verlauf">Verlauf</router-link>
        <span class="sep" />
        <router-link to="/ki" :class="{ 'router-link-active': $route.meta.ai }">KI-Generator</router-link>
      </nav>
      <span class="spacer" />
      <form @submit.prevent="quickSearch">
        <input v-model="quick" class="topsearch" type="search" placeholder="Suche in allen Fragen…" aria-label="Suche in allen Fragen" />
      </form>
      <span class="user">{{ authState.user.email }}</span>
      <button class="secondary small" @click="onLogout">Abmelden</button>
    </header>
    <main class="content">
      <router-view />
    </main>
  </div>
</template>
