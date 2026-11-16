<script setup lang="ts">
import Icon from "../components/Icon.vue";
import { onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { api, ApiError, type QuestionHistory } from "../api";
import { formatDate } from "../bank";

const route = useRoute();
const data = ref<QuestionHistory | null>(null);
const error = ref("");
const loading = ref(true);
const note = ref("");
const notice = ref("");

async function load() {
  loading.value = true;
  error.value = "";
  try {
    data.value = await api.questionHistory(Number(route.params.id));
    note.value = data.value.question.decision_note ?? "";
  } catch (e) {
    data.value = null;
    error.value = e instanceof ApiError && e.status === 404
      ? "Diese Frage gibt es nicht (mehr). Möglicherweise wurde die Datei entfernt, aus der sie stammt."
      : e instanceof ApiError ? e.message : "Die Frage konnte nicht geladen werden.";
  } finally {
    loading.value = false;
  }
}
onMounted(load);
watch(() => route.params.id, load);

async function decide(state: "open" | "reviewed" | "excluded") {
  if (!data.value) return;
  if (state === "excluded" && !confirm("Frage ausschließen? Sie wird nicht gelöscht, aber nicht mehr exportiert oder in Tests verwendet.")) return;
  try {
    await api.decideQuestion(data.value.question.id, state, note.value || undefined);
    notice.value = state === "open" ? "Entscheidung zurückgenommen." : "Entscheidung gespeichert.";
    await load();
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Die Entscheidung konnte nicht gespeichert werden.";
  }
}

const sevLabel = { critical: "Kritisch", review: "Überprüfen", info: "Information" } as const;
const tf = (t: string) => (t === "true" ? "Wahr" : t === "false" ? "Falsch" : t);
</script>

<template>
  <p><router-link to="/bank">← Zur Fragenbank</router-link></p>
  <div v-if="loading" class="muted" role="status"><span class="spinner" /> Lädt…</div>
  <div v-if="error" class="notice error" role="alert">{{ error }}</div>
  <div v-if="notice" class="notice success" role="status">{{ notice }}</div>

  <template v-if="data">
    <div class="page-head">
      <h1>{{ data.question.name ?? "Frage " + data.question.id }}</h1>
      <p>
        {{ data.question.type_name }} · {{ data.question.fach ?? "–" }} / {{ data.question.category ?? "–" }}
        <span v-if="data.question.decision === 'excluded'" class="badge danger">ausgeschlossen</span>
        <span v-else-if="data.question.decision === 'reviewed'" class="badge ok">geprüft</span>
      </p>
    </div>

    <div class="card">
      <p style="margin-top: 0">{{ data.question.text }}</p>
      <ul class="answers-list">
        <li v-for="(a, i) in data.question.answers" :key="i" :class="{ correct: a.is_correct }">
          {{ tf(a.text) }}<span v-if="a.is_correct" class="visually-hidden"> (als richtig markiert)</span>
        </li>
      </ul>
      <p v-if="!data.question.answers.length" class="muted">Dieser Fragetyp hat keine auswertbaren Antwortoptionen. Er wird unverändert mitgeführt.</p>
    </div>

    <div class="card">
      <h2>Ihre Entscheidung</h2>
      <p class="muted" style="margin-top: 0">
        Die Anwendung entscheidet nichts allein. „Geprüft“ blendet die Hinweise zu dieser Frage aus.
        „Ausschließen“ nimmt sie aus Auswahl, Export und Testplanung, ohne sie zu löschen.
      </p>
      <label for="note">Notiz (optional)</label>
      <input id="note" v-model="note" maxlength="500" placeholder="z. B. Absicht: Distraktor-Frage" />
      <div class="row" style="margin-top: 0.6rem">
        <button class="secondary" @click="decide('reviewed')">Geprüft, so lassen</button>
        <button class="secondary" @click="decide('excluded')">Ausschließen</button>
        <button v-if="data.question.decision" class="ghost" @click="decide('open')">Entscheidung zurücknehmen</button>
      </div>
      <p v-if="data.question.decided_at" class="muted">Entschieden am {{ formatDate(data.question.decided_at) }}.</p>
    </div>

    <div v-if="data.findings.length" class="card">
      <h2>Hinweise</h2>
      <div v-for="f in data.findings" :key="f.code + f.detail" style="margin-bottom: 0.8rem">
        <span class="sev" :class="f.severity">{{ sevLabel[f.severity] }}</span> <strong>{{ f.title }}</strong>
        <span v-if="f.done" class="badge ok">erledigt</span>
        <p v-if="f.detail" style="margin: 0.2rem 0"><em>{{ f.detail }}</em></p>
        <p style="margin: 0.2rem 0"><strong>Warum:</strong> {{ f.why }}</p>
        <p style="margin: 0.2rem 0"><strong>Was tun:</strong> {{ f.action }}</p>
      </div>
    </div>

    <div class="card">
      <h2>Herkunft</h2>
      <p v-if="!data.origins.length" class="muted">KI-generiert, nicht aus einer Moodle-Datei.</p>
      <table v-else class="list">
        <thead><tr><th>Datei</th><th>Fach / Kategorie</th><th>Importiert am</th></tr></thead>
        <tbody>
          <tr v-for="o in data.origins" :key="o.filename + o.category">
            <td><router-link :to="{ name: 'bank', query: { file: o.file_id ?? undefined } }">{{ o.filename }}</router-link></td>
            <td>{{ o.fach ?? "–" }} / {{ o.category ?? "–" }}</td>
            <td class="muted">{{ formatDate(o.imported_at) }}</td>
          </tr>
        </tbody>
      </table>
      <p v-if="data.origins.length > 1" class="muted">Diese Frage steht unverändert in {{ data.origins.length }} Dateien und ist hier nur einmal gespeichert.</p>
    </div>

    <div v-if="data.conflict" class="card">
      <h2>Andere Varianten (Widerspruch)</h2>
      <div class="compare">
        <div v-for="v in data.variants" :key="v.id" class="variant">
          <strong>{{ v.label }}</strong>
          <router-link v-if="v.id !== data.question.id" :to="{ name: 'question', params: { id: v.id } }"> öffnen</router-link>
          <span v-else class="muted"> (diese Frage)</span>
          <div v-for="o in v.origins" :key="o.filename" class="muted"><Icon name="file" /> {{ o.filename }}</div>
          <ul class="answers-list">
            <li v-for="(a, i) in v.answers" :key="i" :class="{ correct: a.is_correct, differs: a.differs }">{{ tf(a.text) }}</li>
          </ul>
        </div>
      </div>
      <router-link to="/pruefung" class="button secondary small">Zur Entscheidung →</router-link>
    </div>

    <div v-if="data.similar.length" class="card">
      <h2>Ähnliche Fragen</h2>
      <p class="muted" style="margin-top: 0">Ähnlichkeit wird über gemeinsame Wörter erkannt, nicht über die Bedeutung.</p>
      <ul>
        <li v-for="s in data.similar" :key="s.id">
          <router-link :to="{ name: 'question', params: { id: s.id } }">{{ s.name ?? s.id }}</router-link>
          <span class="badge violet">{{ Math.round(s.score * 100) }} %</span>
          <span class="muted"> {{ s.fach ?? "–" }} / {{ s.category ?? "–" }}</span>
        </li>
      </ul>
    </div>

    <div class="card">
      <h2>In Exporten verwendet</h2>
      <p v-if="!data.exports.length" class="muted">Noch in keinem Export.</p>
      <ul v-else>
        <li v-for="e in data.exports" :key="e.id">
          {{ e.filename }} <span class="muted">· {{ formatDate(e.created_at) }}<template v-if="e.note"> · {{ e.note }}</template></span>
        </li>
      </ul>
    </div>
  </template>
</template>
