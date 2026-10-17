<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api, ApiError, type DocumentOut } from "../api";

const file = ref<File | null>(null);
const documents = ref<DocumentOut[]>([]);
const error = ref("");
const success = ref("");
const busy = ref(false);

async function refresh() {
  documents.value = await api.listDocuments();
}
onMounted(refresh);

function onPick(e: Event) {
  const target = e.target as HTMLInputElement;
  file.value = target.files?.[0] ?? null;
}

async function upload() {
  error.value = "";
  success.value = "";
  if (!file.value) {
    error.value = "Bitte wählen Sie eine Datei (PDF, TXT oder DOCX).";
    return;
  }
  busy.value = true;
  try {
    const doc = await api.uploadDocument(file.value);
    success.value = `„${doc.original_filename}“ wurde hochgeladen und verarbeitet.`;
    file.value = null;
    await refresh();
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Upload fehlgeschlagen.";
  } finally {
    busy.value = false;
  }
}

function kb(n: number) {
  return `${(n / 1024).toFixed(1)} KB`;
}
</script>

<template>
  <h1>Dokument hochladen</h1>
  <div class="card">
    <p class="muted">Erlaubte Formate: PDF, TXT, DOCX. Maximale Größe: 10 MB.</p>
    <div v-if="error" class="notice error">{{ error }}</div>
    <div v-if="success" class="notice success">{{ success }}</div>

    <label for="file">Datei</label>
    <input id="file" type="file" accept=".pdf,.txt,.docx" @change="onPick" />

    <div class="row" style="margin-top: 1rem">
      <button :disabled="busy" @click="upload">
        <span v-if="busy" class="spinner" /> Hochladen
      </button>
    </div>
  </div>

  <div class="card">
    <h2>Hochgeladene Dokumente</h2>
    <p v-if="documents.length === 0" class="muted">Noch keine Dokumente.</p>
    <ul>
      <li v-for="d in documents" :key="d.id">
        <strong>{{ d.original_filename }}</strong>
        <span class="muted"> — {{ d.extension }}, {{ kb(d.size_bytes) }}</span>
      </li>
    </ul>
  </div>
</template>
