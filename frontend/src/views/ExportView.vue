<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api, ApiError, type Question } from "../api";

const approved = ref<Question[]>([]);
const selected = ref<Set<number>>(new Set());
const filename = ref("moodle_fragen");
const error = ref("");
const busy = ref(false);

async function refresh() {
  approved.value = await api.listQuestions("approved");
  selected.value = new Set(approved.value.map((q) => q.id));
}
onMounted(refresh);

function toggle(id: number) {
  if (selected.value.has(id)) selected.value.delete(id);
  else selected.value.add(id);
  // reassign to trigger reactivity for a Set
  selected.value = new Set(selected.value);
}

async function exportXml() {
  error.value = "";
  const ids = [...selected.value];
  if (ids.length === 0) {
    error.value = "Bitte mindestens eine Frage auswählen.";
    return;
  }
  busy.value = true;
  try {
    const blob = await api.exportXml(ids, filename.value);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename.value.endsWith(".xml") ? filename.value : `${filename.value}.xml`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Export fehlgeschlagen.";
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <h1>Moodle-XML exportieren</h1>
  <div class="card">
    <p class="muted">
      Es werden nur <strong>freigegebene</strong> Fragen zum Export angeboten.
      Die erzeugte XML-Datei kann im Moodle-Fragenpool importiert werden
      (siehe Import-Anleitung).
    </p>
    <div v-if="error" class="notice error">{{ error }}</div>

    <p v-if="approved.length === 0" class="notice warn">
      Keine freigegebenen Fragen. Bitte zuerst im Bereich
      <router-link to="/review">„Prüfen“</router-link> Fragen freigeben.
    </p>

    <template v-else>
      <label>Dateiname</label>
      <input v-model="filename" />

      <label>Fragen auswählen</label>
      <div v-for="q in approved" :key="q.id" class="answer">
        <label style="display: flex; gap: 0.5rem; align-items: start; margin: 0; font-weight: 400">
          <input type="checkbox" :checked="selected.has(q.id)" @change="toggle(q.id)" style="width: auto" />
          <span>{{ q.question_text }}</span>
        </label>
      </div>

      <div class="row" style="margin-top: 1rem">
        <button :disabled="busy" @click="exportXml">
          <span v-if="busy" class="spinner" /> {{ selected.size }} Frage(n) exportieren
        </button>
      </div>
    </template>
  </div>
</template>
