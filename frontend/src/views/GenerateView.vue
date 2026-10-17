<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  api,
  ApiError,
  type DocumentOut,
  type Difficulty,
  type Language,
  type QuestionType,
} from "../api";

const router = useRouter();
const documents = ref<DocumentOut[]>([]);
const documentId = ref<number | null>(null);
const questionType = ref<QuestionType>("multiple_choice");
const numQuestions = ref(5);
const difficulty = ref<Difficulty>("medium");
const language = ref<Language>("de");

const error = ref("");
const info = ref("");
const busy = ref(false);

onMounted(async () => {
  documents.value = await api.listDocuments();
  if (documents.value.length) documentId.value = documents.value[0].id;
});

async function generate() {
  error.value = "";
  info.value = "";
  if (!documentId.value) {
    error.value = "Bitte zuerst ein Dokument auswählen oder hochladen.";
    return;
  }
  busy.value = true;
  try {
    const res = await api.generate({
      document_id: documentId.value,
      question_type: questionType.value,
      num_questions: numQuestions.value,
      difficulty: difficulty.value,
      language: language.value,
    });
    info.value =
      `${res.created.length} Frage(n) erstellt (Anbieter: ${res.provider}). ` +
      `Jetzt im Bereich „Prüfen“ freigeben.`;
    if (res.parse_errors.length) {
      info.value += ` Hinweis: ${res.parse_errors.length} ungültige Antwort(en) verworfen.`;
    }
    setTimeout(() => router.push({ name: "review" }), 900);
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Generierung fehlgeschlagen.";
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <h1>Fragen generieren</h1>
  <div class="card">
    <div v-if="error" class="notice error">{{ error }}</div>
    <div v-if="info" class="notice success">{{ info }}</div>

    <p v-if="documents.length === 0" class="notice warn">
      Es gibt noch keine Dokumente. Bitte zuerst <router-link to="/upload">ein Dokument hochladen</router-link>.
    </p>

    <label for="doc">Dokument</label>
    <select id="doc" v-model.number="documentId">
      <option v-for="d in documents" :key="d.id" :value="d.id">{{ d.original_filename }}</option>
    </select>

    <div class="grid-2">
      <div>
        <label for="type">Fragetyp</label>
        <select id="type" v-model="questionType">
          <option value="multiple_choice">Multiple Choice</option>
          <option value="true_false">Wahr / Falsch</option>
          <option value="short_answer">Kurzantwort</option>
        </select>
      </div>
      <div>
        <label for="count">Anzahl Fragen</label>
        <input id="count" type="number" v-model.number="numQuestions" min="1" max="50" />
      </div>
      <div>
        <label for="diff">Schwierigkeit</label>
        <select id="diff" v-model="difficulty">
          <option value="easy">Leicht</option>
          <option value="medium">Mittel</option>
          <option value="hard">Schwer</option>
        </select>
      </div>
      <div>
        <label for="lang">Sprache</label>
        <select id="lang" v-model="language">
          <option value="de">Deutsch</option>
          <option value="en">Englisch</option>
        </select>
      </div>
    </div>

    <div class="row" style="margin-top: 1rem">
      <button :disabled="busy || documents.length === 0" @click="generate">
        <span v-if="busy" class="spinner" /> Generieren
      </button>
    </div>
  </div>
</template>
