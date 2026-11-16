<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { api, ApiError, type ConflictGroup, type FindingsPage, type Severity } from "../api";
import { formatDate, formatNumber } from "../bank";

const SEV_LABEL: Record<Severity, string> = { critical: "Kritisch", review: "Überprüfen", info: "Information" };
const SEV_ICON: Record<Severity, string> = { critical: "⛔", review: "⚠️", info: "ℹ️" };
const SEVS: Severity[] = ["critical", "review", "info"];

const page = ref<FindingsPage | null>(null);
const conflicts = ref<ConflictGroup[]>([]);
const severity = ref<Severity | "">("");
const state = ref<"open" | "done">("open");
const pageNo = ref(1);
const loading = ref(true);
const error = ref("");
const notes = ref<Record<string, string>>({});

async function load() {
  error.value = "";
  try {
    const [f, c] = await Promise.all([
      api.findings({ severity: severity.value || undefined, state: state.value, page: pageNo.value, page_size: 30 }),
      api.conflicts(state.value),
    ]);
    page.value = f;
    conflicts.value = c.items;
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Die Hinweise konnten nicht geladen werden.";
  } finally {
    loading.value = false;
  }
}
onMounted(load);
watch([severity, state], () => { pageNo.value = 1; load(); });

const showConflicts = computed(() => conflicts.value.length > 0 && (severity.value === "" || severity.value === "critical"));
// Contradictions have their own section (side by side), so they are not repeated in the list.
const items = computed(() => (page.value?.items ?? []).filter((f) => f.code !== "conflict"));
const pages = computed(() => Math.max(1, Math.ceil((page.value?.total ?? 0) / 30)));

async function act(fn: () => Promise<unknown>, okText: string) {
  error.value = "";
  try {
    await fn();
    status.value = okText;
    await load();
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Die Entscheidung konnte nicht gespeichert werden.";
  }
}
const status = ref("");

const showTrueFalse = (t: string) => (t === "true" ? "Wahr" : t === "false" ? "Falsch" : t);

function keep(g: ConflictGroup, id: number | null) {
  const msg = id === null
    ? "Alle Varianten bleiben erhalten. Sie werden in einem Test nie zusammen verwendet. Fortfahren?"
    : "Nur diese Variante bleibt. Die anderen werden ausgeschlossen (nicht gelöscht) und nicht mehr exportiert oder in Tests verwendet. Fortfahren?";
  if (!confirm(msg)) return;
  act(() => api.decideConflict(g.key, id, notes.value[g.key]), "Entscheidung gespeichert. Sie können sie jederzeit zurücknehmen.");
}

function mark(id: number, name: string | null, decision: "reviewed" | "excluded" | "open") {
  if (decision === "excluded" && !confirm(`„${name ?? id}“ ausschließen? Die Frage wird nicht gelöscht, aber nicht mehr exportiert oder in Tests verwendet.`)) return;
  act(() => api.decideQuestion(id, decision), decision === "open" ? "Entscheidung zurückgenommen." : "Entscheidung gespeichert.");
}
</script>

<template>
  <div class="page-head">
    <h1>Qualität der Fragenbank</h1>
    <p>
      Hinweise auf mögliche Probleme, nach Dringlichkeit sortiert. Die Anwendung <strong>entscheidet nie selbst</strong>,
      welche Antwort fachlich richtig ist. Sie zeigt, was auffällt, und Sie entscheiden.
    </p>
  </div>

  <div v-if="loading" class="muted" role="status"><span class="spinner" /> Lädt…</div>
  <div v-if="error" class="notice error" role="alert">{{ error }}</div>
  <div v-if="status" class="notice success" role="status">{{ status }}</div>

  <template v-if="page">
    <div class="stats">
      <button v-for="s in SEVS" :key="s" class="stat" :class="s === 'critical' ? 'danger' : s === 'review' ? 'warn' : ''"
              :aria-pressed="severity === s" style="text-align: left; cursor: pointer"
              @click="severity = severity === s ? '' : s">
        <div class="value">{{ formatNumber(page.summary.open[s]) }}</div>
        <div class="label">{{ SEV_ICON[s] }} {{ SEV_LABEL[s] }} · offen<span v-if="page.summary.done[s]"> ({{ page.summary.done[s] }} erledigt)</span></div>
      </button>
    </div>

    <div class="tabs" role="group" aria-label="Status">
      <button :class="{ active: state === 'open' }" @click="state = 'open'">Offen</button>
      <button :class="{ active: state === 'done' }" @click="state = 'done'">Erledigt</button>
      <button v-if="severity" class="ghost" @click="severity = ''">Filter „{{ SEV_LABEL[severity] }}“ aufheben</button>
    </div>

    <div v-if="!showConflicts && items.length === 0" class="card empty">
      <div class="icon">✅</div>
      <h2>{{ state === "open" ? "Nichts Offenes" : "Noch nichts erledigt" }}</h2>
      <p v-if="state === 'open'">Für diese Auswahl liegen keine offenen Hinweise vor. Das ist keine Garantie, dass die Fragen fachlich korrekt sind, nur dass die automatischen Prüfungen nichts gefunden haben.</p>
      <p v-else>Wenn Sie einen Hinweis als „geprüft“ markieren oder eine Frage ausschließen, erscheint er hier.</p>
    </div>

    <!-- contradictions: variants side by side -->
    <section v-if="showConflicts" aria-labelledby="conf-h">
      <h2 id="conf-h"><span class="sev critical">⛔ Kritisch</span> Widersprüche: gleiche Frage, andere richtige Antwort</h2>
      <p class="muted">
        Beide Varianten haben denselben Fragetext, aber unterschiedliche richtige Antworten.
        Gelb umrandet sind die Antworten, die sich unterscheiden. Welche stimmt, kann nur Ihr Fachwissen klären.
      </p>
      <div v-for="g in conflicts" :key="g.key" class="card">
        <h3>„{{ g.text }}“</h3>
        <div class="compare">
          <div v-for="v in g.variants" :key="v.id" class="variant" :class="{ out: v.decision === 'excluded', kept: g.resolved && v.decision === 'reviewed' }">
            <div class="card-head" style="margin-bottom: 0.4rem">
              <strong>{{ v.label }}</strong>
              <span v-if="v.decision === 'excluded'" class="badge danger">ausgeschlossen</span>
              <span v-else-if="v.decision === 'reviewed'" class="badge ok">bleibt</span>
            </div>
            <div v-for="o in v.origins" :key="o.filename" class="muted">
              📄 {{ o.filename }} · {{ o.category ?? "–" }} · importiert {{ formatDate(o.imported_at) }}
            </div>
            <ul class="answers-list">
              <li v-for="(a, i) in v.answers" :key="i" :class="{ correct: a.is_correct, differs: a.differs }">
                {{ showTrueFalse(a.text) }}<span v-if="a.is_correct" class="visually-hidden"> (als richtig markiert)</span>
              </li>
            </ul>
            <p v-if="v.decision_note" class="muted">Notiz: {{ v.decision_note }}</p>
            <div class="row" v-if="!g.resolved">
              <button class="small" @click="keep(g, v.id)">Diese Variante bleibt</button>
              <router-link class="button ghost small" :to="{ name: 'question', params: { id: v.id } }">Verlauf</router-link>
            </div>
          </div>
        </div>
        <div v-if="!g.resolved" class="row" style="margin-top: 0.6rem">
          <input v-model="notes[g.key]" placeholder="Notiz (optional), z. B. „Folie 12 gilt“" aria-label="Notiz zur Entscheidung" style="max-width: 360px" />
          <button class="secondary small" @click="keep(g, null)">Alle bleiben (nie gemeinsam im Test)</button>
        </div>
        <div v-else class="row" style="margin-top: 0.6rem">
          <button class="secondary small" @click="act(() => api.reopenConflict(g.key), 'Entscheidung zurückgenommen.')">Entscheidung zurücknehmen</button>
        </div>
      </div>
    </section>

    <!-- all other findings -->
    <section v-if="items.length">
      <h2>Weitere Hinweise</h2>
      <div v-for="f in items" :key="f.code + f.question_id" class="card tight">
        <div class="card-head" style="margin-bottom: 0.3rem">
          <span class="sev" :class="f.severity">{{ SEV_ICON[f.severity] }} {{ SEV_LABEL[f.severity] }}</span>
          <strong>{{ page.catalog[f.code].title }}</strong>
        </div>
        <router-link :to="{ name: 'question', params: { id: f.question_id } }"><strong>{{ f.question.name ?? "Frage " + f.question_id }}</strong></router-link>
        <span class="muted"> · {{ f.question.type_name }} · {{ f.question.fach ?? "–" }} / {{ f.question.category ?? "–" }}</span>
        <p v-if="f.detail" style="margin: 0.3rem 0"><em>{{ f.detail }}</em></p>
        <p class="muted" style="margin: 0.2rem 0">{{ f.question.text }}</p>
        <details>
          <summary>Warum ist das ein Hinweis, und was tun?</summary>
          <p style="margin: 0.4rem 0"><strong>Warum:</strong> {{ page.catalog[f.code].why }}</p>
          <p style="margin: 0.2rem 0"><strong>Was tun:</strong> {{ page.catalog[f.code].action }}</p>
        </details>
        <div class="row" style="margin-top: 0.5rem">
          <template v-if="state === 'open'">
            <button class="secondary small" @click="mark(f.question_id, f.question.name, 'reviewed')">Geprüft, so lassen</button>
            <button class="ghost small" @click="mark(f.question_id, f.question.name, 'excluded')">Ausschließen</button>
          </template>
          <template v-else>
            <span class="badge" :class="f.decision === 'excluded' ? 'danger' : 'ok'">{{ f.decision === "excluded" ? "ausgeschlossen" : "geprüft" }}</span>
            <button class="secondary small" @click="mark(f.question_id, f.question.name, 'open')">Zurücknehmen</button>
          </template>
        </div>
      </div>
      <div v-if="pages > 1" class="pager">
        <button class="secondary small" :disabled="pageNo <= 1" @click="pageNo--; load()">← Zurück</button>
        <span>Seite {{ pageNo }} von {{ pages }}</span>
        <button class="secondary small" :disabled="pageNo >= pages" @click="pageNo++; load()">Weiter →</button>
      </div>
    </section>
  </template>
</template>
