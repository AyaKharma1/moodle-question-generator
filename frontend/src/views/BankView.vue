<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  api,
  ApiError,
  type BankAnalysis,
  type BankOverview,
  type ImportFile,
  type Question,
} from "../api";
import { answerText, downloadBlob, plainText, selection, setSelected, shortText, toggleSelected, typeLabel } from "../bank";

const route = useRoute();
const router = useRouter();

const questions = ref<Question[]>([]);
const overview = ref<BankOverview | null>(null);
const analysis = ref<BankAnalysis | null>(null);
const files = ref<ImportFile[]>([]);
const loading = ref(true);
const expanded = ref<Set<number>>(new Set());

const search = ref(String(route.query.q ?? ""));
const filename = ref("moodle_fragen");
const error = ref("");
const success = ref("");
const busy = ref(false);

const filter = computed(() => ({
  fach: (route.query.fach as string) || undefined,
  category: (route.query.category as string) || undefined,
  import_file_id: route.query.file ? Number(route.query.file) : undefined,
  source: (route.query.source as "import" | "ai") || undefined,
  q: (route.query.q as string) || undefined,
}));

function setQuery(key: string, value: string | number | undefined) {
  const query = { ...route.query, [key]: value === "" || value === undefined ? undefined : String(value) };
  if (key === "fach") query.category = undefined;
  router.replace({ query });
}

let searchTimer: ReturnType<typeof setTimeout> | undefined;
watch(search, (value) => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => setQuery("q", value.trim()), 300);
});

async function loadQuestions() {
  loading.value = true;
  try {
    questions.value = await api.listQuestions(filter.value);
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  [overview.value, analysis.value, files.value] = await Promise.all([
    api.overview(), api.analysis(), api.listImportFiles(),
  ]);
  await loadQuestions();
});
watch(filter, loadQuestions);

const categories = computed(() => {
  const tree = overview.value?.tree ?? [];
  const chosen = filter.value.fach;
  return tree.filter((f) => !chosen || f.fach === chosen).flatMap((f) => f.categories.map((c) => c.name));
});

// Warnings per question id, from the bank analysis.
const flags = computed(() => {
  const map = new Map<number, { label: string; cls: string }[]>();
  const add = (id: number, label: string, cls: string) => {
    if (!map.has(id)) map.set(id, []);
    map.get(id)!.push({ label, cls });
  };
  const a = analysis.value;
  if (!a) return map;
  for (const e of a.exact) add(e.question.id, `in ${e.count} Dateien`, "info");
  for (const g of a.conflicts) for (const q of g.questions) add(q.id, "Widerspruch", "danger");
  for (const p of a.similar) {
    add(p.a.id, "ähnliche Frage", "violet");
    add(p.b.id, "ähnliche Frage", "violet");
  }
  for (const i of a.issues) add(i.question.id, i.problems[0], "warn");
  return map;
});

const selectedIds = computed(() => [...selection.ids]);
const allVisibleSelected = computed(
  () => questions.value.length > 0 && questions.value.every((q) => selection.ids.has(q.id)),
);

// Things that would make the exported test unfair or broken.
const selectionWarnings = computed(() => {
  const a = analysis.value;
  const ids = selection.ids;
  const warnings: string[] = [];
  if (!a || ids.size === 0) return warnings;
  const similar = a.similar.filter((p) => ids.has(p.a.id) && ids.has(p.b.id)).length;
  const conflicts = a.conflicts.filter((g) => g.questions.filter((q) => ids.has(q.id)).length > 1).length;
  if (similar) warnings.push(`${similar} Paar(e) sehr ähnlicher Fragen ausgewählt: Studierende könnten fast dieselbe Frage zweimal bekommen.`);
  if (conflicts) warnings.push(`${conflicts} widersprüchliche Frage(n) doppelt ausgewählt (gleicher Text, andere Antwort).`);
  return warnings;
});

function toggleAll() {
  setSelected(questions.value.map((q) => q.id), !allVisibleSelected.value);
}

function toggleExpanded(id: number) {
  const next = new Set(expanded.value);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  expanded.value = next;
}

async function exportSelected() {
  error.value = "";
  success.value = "";
  busy.value = true;
  try {
    const name = filename.value.trim() || "moodle_fragen";
    const blob = await api.exportXml(selectedIds.value, name);
    downloadBlob(blob, name.endsWith(".xml") ? name : `${name}.xml`);
    success.value = `${selection.ids.size} Frage(n) als „${name}.xml“ exportiert. In Moodle: Fragensammlung → Importieren → Moodle-XML.`;
    setSelected(selectedIds.value, false);
    await loadQuestions();
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Export fehlgeschlagen.";
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div class="page-head">
    <h1>Fragenbank</h1>
    <p>Alle Fragen mit Herkunft. Filtern, Fragen auswählen und als Moodle-XML exportieren, mit Kategorien und ohne Duplikate.</p>
  </div>

  <div class="card">
    <div class="filters">
      <div>
        <label for="q">Suche</label>
        <input id="q" v-model="search" placeholder="Fragetext oder Name…" />
      </div>
      <div>
        <label for="fach">Fach</label>
        <select id="fach" :value="filter.fach ?? ''" @change="setQuery('fach', ($event.target as HTMLSelectElement).value)">
          <option value="">Alle Fächer</option>
          <option v-for="f in overview?.tree ?? []" :key="f.fach" :value="f.fach">{{ f.fach }}</option>
        </select>
      </div>
      <div>
        <label for="cat">Kategorie</label>
        <select id="cat" :value="filter.category ?? ''" @change="setQuery('category', ($event.target as HTMLSelectElement).value)">
          <option value="">Alle Kategorien</option>
          <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
        </select>
      </div>
      <div>
        <label for="file">Datei</label>
        <select id="file" :value="filter.import_file_id ?? ''" @change="setQuery('file', ($event.target as HTMLSelectElement).value)">
          <option value="">Alle Dateien</option>
          <option v-for="f in files" :key="f.id" :value="f.id">{{ f.filename }}</option>
        </select>
      </div>
      <div>
        <label for="src">Quelle</label>
        <select id="src" :value="filter.source ?? ''" @change="setQuery('source', ($event.target as HTMLSelectElement).value)">
          <option value="">Alle</option>
          <option value="import">Aus Moodle importiert</option>
          <option value="ai">KI-generiert</option>
        </select>
      </div>
    </div>
  </div>

  <div v-if="error" class="notice error">{{ error }}</div>
  <div v-if="success" class="notice success">{{ success }}</div>

  <div class="card-head">
    <span class="muted">{{ loading ? "Lädt…" : `${questions.length} Frage(n)` }}</span>
    <button v-if="questions.length" class="secondary small" @click="toggleAll">
      {{ allVisibleSelected ? "Auswahl aufheben" : "Alle angezeigten auswählen" }}
    </button>
  </div>

  <div v-if="!loading && questions.length === 0" class="card empty">
    <div class="icon">🔍</div>
    <p v-if="overview?.totals.questions">Keine Fragen für diesen Filter.</p>
    <p v-else>Noch keine Fragen. <router-link to="/import">Jetzt Moodle-XML importieren →</router-link></p>
  </div>

  <div v-for="q in questions" :key="q.id" class="card tight q-card">
    <input type="checkbox" :checked="selection.ids.has(q.id)" :disabled="q.status !== 'approved'"
           :title="q.status !== 'approved' ? 'Nur freigegebene Fragen können exportiert werden' : 'Für den Export auswählen'"
           @change="toggleSelected(q.id)" style="margin-top: 0.3rem" />
    <div>
      <div class="meta">
        <span class="q-title">{{ q.name || "Ohne Namen" }}</span>
        <span class="badge neutral">{{ typeLabel(q.question_type) }}</span>
        <span v-if="q.ai_generated" class="badge violet">KI</span>
        <span v-if="q.status !== 'approved'" class="badge" :class="q.status">{{ q.status === "pending" ? "noch nicht freigegeben" : "abgelehnt" }}</span>
        <span v-for="f in flags.get(q.id) ?? []" :key="f.label" class="badge" :class="f.cls">{{ f.label }}</span>
      </div>
      <div class="q-text">{{ expanded.has(q.id) ? plainText(q.question_text) : shortText(plainText(q.question_text)) }}</div>
      <div class="chips">
        <span class="chip" v-if="q.fach">📚 <strong>{{ q.fach }}</strong> / {{ q.category }}</span>
        <span v-for="o in q.origins" :key="o.file_id + (o.category ?? '')" class="chip" :title="o.category ?? ''">📄 {{ o.filename }}</span>
        <span v-if="!q.origins.length && q.ai_generated" class="chip">🤖 aus Vorlesungsmaterial generiert</span>
        <span v-for="e in q.exported_in" :key="e" class="chip export">⬆ exportiert in {{ e }}</span>
      </div>
      <button v-if="q.answers.length || plainText(q.question_text).length > 280" class="ghost small"
              style="margin-top: 0.35rem; padding-left: 0" @click="toggleExpanded(q.id)">
        {{ expanded.has(q.id) ? "Weniger anzeigen" : q.answers.length ? `Ganzen Text und ${q.answers.length} Antwort(en) anzeigen` : "Ganzen Text anzeigen" }}
      </button>
      <ul v-if="expanded.has(q.id)" class="answers-list">
        <li v-for="a in q.answers" :key="a.id" :class="{ correct: a.is_correct }">{{ answerText(a.text, q.question_type) }}</li>
      </ul>
    </div>
  </div>

  <div v-if="selection.ids.size" class="selection-bar">
    <strong>{{ selection.ids.size }} ausgewählt</strong>
    <button class="ghost small" style="color: #fff" @click="setSelected(selectedIds, false)">Auswahl leeren</button>
    <span class="grow" />
    <input v-model="filename" placeholder="Dateiname" aria-label="Dateiname" />
    <button :disabled="busy" @click="exportSelected">
      <span v-if="busy" class="spinner" /> Als Moodle-XML exportieren
    </button>
    <div v-for="w in selectionWarnings" :key="w" class="warn">⚠ {{ w }}</div>
  </div>
</template>
