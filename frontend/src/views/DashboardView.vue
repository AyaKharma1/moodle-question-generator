<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api, type DocumentOut, type Question } from "../api";

const documents = ref<DocumentOut[]>([]);
const questions = ref<Question[]>([]);
const loading = ref(true);

onMounted(async () => {
  try {
    [documents.value, questions.value] = await Promise.all([
      api.listDocuments(),
      api.listQuestions(),
    ]);
  } finally {
    loading.value = false;
  }
});

function count(status: string) {
  return questions.value.filter((q) => q.status === status).length;
}
</script>

<template>
  <h1>Dashboard</h1>
  <div class="steps">
    <span class="step">1 · Upload</span>
    <span class="step">2 · Generieren</span>
    <span class="step">3 · Prüfen & Freigeben</span>
    <span class="step">4 · Export</span>
  </div>

  <div v-if="loading" class="muted">Lädt…</div>
  <template v-else>
    <div class="grid-2">
      <div class="card">
        <h2>Dokumente</h2>
        <p style="font-size: 2rem; font-weight: 700">{{ documents.length }}</p>
        <router-link to="/upload">Dokument hochladen →</router-link>
      </div>
      <div class="card">
        <h2>Fragen</h2>
        <p class="row">
          <span class="badge pending">{{ count("pending") }} offen</span>
          <span class="badge approved">{{ count("approved") }} freigegeben</span>
          <span class="badge rejected">{{ count("rejected") }} abgelehnt</span>
        </p>
        <router-link to="/review">Zur Prüfung →</router-link>
      </div>
    </div>

    <div class="card">
      <h2>Workflow</h2>
      <p class="muted">
        Laden Sie Vorlesungsmaterial hoch, lassen Sie Fragen generieren, prüfen und
        bearbeiten Sie diese, geben Sie geeignete Fragen frei und exportieren Sie sie
        als Moodle-XML. Es werden nur <strong>freigegebene</strong> Fragen exportiert.
      </p>
    </div>
  </template>
</template>
