<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { api, ApiError } from "../api";
import { login } from "../auth";

const router = useRouter();
const mode = ref<"login" | "register">("login");
const email = ref("");
const password = ref("");
const fullName = ref("");
const error = ref("");
const busy = ref(false);

async function submit() {
  error.value = "";
  busy.value = true;
  try {
    if (mode.value === "register") {
      await api.register(email.value, password.value, fullName.value || undefined);
    }
    await login(email.value, password.value);
    router.push({ name: "dashboard" });
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Unbekannter Fehler";
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div style="max-width: 420px; margin: 3rem auto">
    <div class="card">
      <h1>{{ mode === "login" ? "Anmelden" : "Registrieren" }}</h1>
      <p class="muted">Sicherer KI-gestützter Moodle-Fragengenerator</p>

      <div v-if="error" class="notice error">{{ error }}</div>

      <form @submit.prevent="submit">
        <template v-if="mode === 'register'">
          <label for="name">Name (optional)</label>
          <input id="name" v-model="fullName" autocomplete="name" />
        </template>

        <label for="email">E-Mail</label>
        <input id="email" v-model="email" type="email" required autocomplete="username" />

        <label for="pw">Passwort</label>
        <input id="pw" v-model="password" type="password" required minlength="8"
               autocomplete="current-password" />

        <div class="row" style="margin-top: 1rem">
          <button type="submit" :disabled="busy">
            <span v-if="busy" class="spinner" /> {{ mode === "login" ? "Anmelden" : "Konto erstellen" }}
          </button>
          <button type="button" class="secondary"
                  @click="mode = mode === 'login' ? 'register' : 'login'">
            {{ mode === "login" ? "Neues Konto" : "Zurück zum Login" }}
          </button>
        </div>
      </form>
      <p class="muted" style="margin-top: 1rem">
        Das Passwort muss mindestens 8 Zeichen lang sein.
      </p>
    </div>
  </div>
</template>
