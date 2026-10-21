<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { api, ApiError, type Question } from "../api";

const questions = ref<Question[]>([]);
const loading = ref(true);
const error = ref("");
// Local editable copies keyed by question id.
const edits = reactive<Record<number, Question>>({});

async function refresh() {
  loading.value = true;
  try {
  const list = await api.listQuestions();
    for (const q of list) edits[q.id] = structuredClone(q);
    questions.value = list;
  } finally {
    loading.value = false;
  }
}
onMounted(refresh);

const typeLabel: Record<string, string> = {
  multiple_choice: "Multiple Choice",
  true_false: "Wahr / Falsch",
  short_answer: "Kurzantwort",
};

async function save(q: Question) {
  error.value = "";
  const e = edits[q.id];
  try {
    const updated = await api.updateQuestion(q.id, {
      question_text: e.question_text,
      explanation: e.explanation,
      difficulty: e.difficulty,
      language: e.language,
      answers: e.answers.map((a) => ({
        text: a.text,
        is_correct: a.is_correct,
        feedback: a.feedback,
      })),
    });
    Object.assign(q, updated);
    edits[q.id] = structuredClone(updated);
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : "Speichern fehlgeschlagen.";
  }
}

async function review(q: Question, action: "approve" | "reject") {
  error.value = "";
  try {
    const updated = await api.review(q.id, action);
    Object.assign(q, updated);
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : "Aktion fehlgeschlagen.";
  }
}

async function regenerate(q: Question) {
  try {
    await api.regenerate(q.id);
    await refresh();
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : "Neu generieren fehlgeschlagen.";
  }
}

async function remove(q: Question) {
  if (!confirm("Diese Frage wirklich löschen?")) return;
  await api.deleteQuestion(q.id);
  await refresh();
}
</script>

<template>
  <h1>Fragen prüfen & freigeben</h1>
  <p class="muted">
    Jede KI-generierte Frage muss vor dem Export freigegeben werden.
    Bearbeiten Sie bei Bedarf Text und Antworten. Bearbeitete Fragen gehen zurück in den Status „offen“.
  </p>

  <div v-if="error" class="notice error">{{ error }}</div>
  <div v-if="loading" class="muted">Lädt…</div>
  <p v-else-if="questions.length === 0" class="muted">
    Keine Fragen vorhanden. <router-link to="/generate">Jetzt generieren →</router-link>
  </p>

  <div v-for="q in questions" :key="q.id" class="card">
    <div class="row" style="justify-content: space-between">
      <span>
        <span class="badge" :class="q.status">{{ q.status }}</span>
        <span class="muted"> · {{ typeLabel[q.question_type] }}</span>
      </span>
      <span class="muted">
        Grounding: {{ (q.grounding_score * 100).toFixed(0) }}%
        <span v-if="q.is_duplicate" class="badge rejected">Duplikat</span>
      </span>
    </div>

    <label>Fragetext</label>
    <textarea v-model="edits[q.id].question_text" />

    <label>Antworten</label>
    <div v-for="(a, i) in edits[q.id].answers" :key="i"
         class="answer" :class="{ correct: a.is_correct }">
      <div class="row">
        <input v-model="a.text" style="flex: 1" />
        <label style="margin: 0; display: flex; gap: 0.35rem; align-items: center">
          <input type="checkbox" v-model="a.is_correct" style="width: auto" /> richtig
        </label>
      </div>
      <input v-model="a.feedback" placeholder="Feedback (optional)" style="margin-top: 0.4rem" />
    </div>

    <label>Erklärung</label>
    <textarea v-model="edits[q.id].explanation" />

    <div class="row" style="margin-top: 0.75rem">
      <button class="secondary small" @click="save(q)">Speichern</button>
      <button class="ok small" @click="review(q, 'approve')" :disabled="q.status === 'approved'">Freigeben</button>
      <button class="secondary small" @click="review(q, 'reject')" :disabled="q.status === 'rejected'">Ablehnen</button>
      <button class="secondary small" @click="regenerate(q)">Neu generieren</button>
      <button class="danger small" @click="remove(q)">Löschen</button>
    </div>
  </div>
</template>
