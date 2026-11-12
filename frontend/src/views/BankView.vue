<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api, ApiError, type BankPage, type BankQuery, type FacetValue, type SelectionCheck } from "../api";
import {
  answerText, downloadBlob, excerpt, FLAG_LABELS, formatNumber, highlight, matchFields, plainText, searchTerms,
  selection, setSelected, SORT_LABELS, toggleSelected, typeLabel,
} from "../bank";

const route = useRoute();
const router = useRouter();

const result = ref<BankPage | null>(null);
const check = ref<SelectionCheck | null>(null);
const loading = ref(true);
const expanded = ref<Set<number>>(new Set());

function str(v: unknown): string {
  return typeof v === "string" ? v : "";
}

const search = ref(str(route.query.q));
const filename = ref("moodle_fragen");
const prefix = ref("");
const randomCount = ref(10);
const error = ref("");
const success = ref("");
const busy = ref(false);

// All filters live in the URL, so a search can be bookmarked and the back button works.
const query = computed<BankQuery>(() => ({
  q: str(route.query.q) || undefined,
  fach: str(route.query.fach) || undefined,
  category: str(route.query.category) || undefined,
  file: str(route.query.file) || undefined,
  type: str(route.query.type) || undefined,
  source: str(route.query.source) || undefined,
  flag: str(route.query.flag) || undefined,
  exported: str(route.query.exported) || undefined,
  sort: str(route.query.sort) || "newest",
  page: Number(route.query.page) || 1,
  page_size: Number(route.query.size) || 50,
}));
const terms = computed(() => searchTerms(query.value.q));

function setQuery(updates: Record<string, string | number | undefined>) {
  const next: Record<string, string | undefined> = {};
  for (const [k, v] of Object.entries(route.query)) next[k] = typeof v === "string" ? v : undefined;
  for (const [k, v] of Object.entries(updates)) next[k] = v === undefined || v === "" ? undefined : String(v);
  if (!("page" in updates)) next.page = undefined;   // a new filter starts on page 1
  router.replace({ query: next });
}

let loadId = 0;
async function load() {
  const id = ++loadId;
  loading.value = true;
  try {
    const page = await api.bankQuestions(query.value);
    if (id === loadId) result.value = page;
  } catch (e) {
    if (id === loadId) error.value = e instanceof ApiError ? e.message : "Suche fehlgeschlagen.";
  } finally {
    if (id === loadId) loading.value = false;
  }
}
watch(query, load, { immediate: true });

let searchTimer: ReturnType<typeof setTimeout> | undefined;
watch(search, (value) => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => setQuery({ q: value.trim() }), 300);
});
// the search box in the top bar changes the URL from outside
watch(() => route.query.q, (value) => {
  if (str(value) !== search.value.trim()) search.value = str(value);
});

// ---------- filters ----------

function withCurrent(values: FacetValue[] | undefined, current: string | undefined): FacetValue[] {
  const list = values ?? [];
  return current && !list.some((v) => v.value === current) ? [{ value: current, count: 0 }, ...list] : list;
}
const fachOptions = computed(() => withCurrent(result.value?.facets.fach, query.value.fach));
const categoryOptions = computed(() => withCurrent(result.value?.facets.category, query.value.category));
const typeOptions = computed(() => withCurrent(result.value?.facets.type, query.value.type));
const fileOptions = computed(() => result.value?.facets.file ?? []);

const activeFilters = computed(() => {
  const q = query.value;
  const fileName = fileOptions.value.find((f) => String(f.id) === String(q.file))?.value ?? `Datei ${q.file}`;
  return [
    q.fach && { key: "fach", label: `Fach: ${q.fach}` },
    q.category && { key: "category", label: `Kategorie: ${q.category}` },
    q.file && { key: "file", label: `Datei: ${fileName}` },
    q.type && { key: "type", label: `Typ: ${typeLabel(q.type)}` },
    q.source && { key: "source", label: q.source === "ai" ? "Nur KI-generiert" : "Nur aus Moodle importiert" },
    q.flag && { key: "flag", label: `Hinweis: ${FLAG_LABELS[q.flag] ?? q.flag}` },
    q.exported && { key: "exported", label: q.exported === "no" ? "Noch nie aus der App exportiert" : "Schon aus der App exportiert" },
  ].filter(Boolean) as { key: string; label: string }[];
});

function resetFilters() {
  search.value = "";
  router.replace({ query: {} });
}

// ---------- what is on the page ----------

const items = computed(() => result.value?.items ?? []);
const plain = computed(() => new Map(items.value.map((q) => [q.id, plainText(q.question_text)])));
const hits = computed(() => new Map(items.value.map((q) => [q.id, matchFields(q, terms.value)])));

function body(id: number): string {
  const text = plain.value.get(id) ?? "";
  return expanded.value.has(id) ? text : excerpt(text, terms.value);
}
function isLong(id: number): boolean {
  return (plain.value.get(id) ?? "").length > 280;
}
function toggleExpanded(id: number) {
  const next = new Set(expanded.value);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  expanded.value = next;
}

// ---------- paging ----------

const first = computed(() => (result.value ? (result.value.page - 1) * result.value.page_size + 1 : 0));
const last = computed(() => (result.value ? first.value + items.value.length - 1 : 0));
function goTo(page: number) {
  setQuery({ page });
  window.scrollTo({ top: 0 });
}

// ---------- selection ----------

const selectedIds = computed(() => [...selection.ids]);
const selectableOnPage = computed(() => items.value.filter((q) => q.status === "approved").map((q) => q.id));
const pageAllSelected = computed(
  () => selectableOnPage.value.length > 0 && selectableOnPage.value.every((id) => selection.ids.has(id)),
);

// The server checks the picked questions together (similar, contradicting, broken).
let checkTimer: ReturnType<typeof setTimeout> | undefined;
watch(() => selection.ids, (ids) => {
  clearTimeout(checkTimer);
  if (ids.size === 0) {
    check.value = null;
    return;
  }
  checkTimer = setTimeout(async () => {
    try {
      check.value = await api.checkSelection([...ids]);
    } catch {
      check.value = null;
    }
  }, 400);
});

const selectionWarnings = computed(() => {
  const c = check.value;
  const warnings: string[] = [];
  if (!c) return warnings;
  if (c.similar_pairs) warnings.push(`${c.similar_pairs} Paar(e) sehr ähnlicher Fragen ausgewählt (${c.similar_examples.join("; ")}): Studierende könnten fast dieselbe Frage zweimal bekommen.`);
  if (c.conflict_groups) warnings.push(`${c.conflict_groups} widersprüchliche Frage(n) doppelt ausgewählt, z. B. „${c.conflict_examples[0]}“ (gleicher Text, andere Antwort).`);
  if (c.broken) warnings.push(`${c.broken} fehlerhafte Frage(n) ausgewählt, z. B. „${c.broken_examples[0]}“.`);
  return warnings;
});

function toggleThisPage() {
  setSelected(selectableOnPage.value, !pageAllSelected.value);
}

async function guarded(action: () => Promise<void>, fallback: string) {
  error.value = "";
  success.value = "";
  busy.value = true;
  try {
    await action();
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : fallback;
  } finally {
    busy.value = false;
  }
}

function selectAllResults() {
  return guarded(async () => {
    const res = await api.bankSelectableIds(query.value);
    setSelected(res.ids, true);
    success.value = `${formatNumber(res.total)} Frage(n) ausgewählt` +
      (res.truncated ? ` (Obergrenze erreicht, bitte den Filter enger setzen)` : ".");
  }, "Auswahl fehlgeschlagen.");
}

function randomPick() {
  return guarded(async () => {
    const res = await api.bankSelectableIds(query.value, true);
    const ids = [...res.ids];
    for (let i = ids.length - 1; i > 0; i--) {          // Fisher-Yates shuffle
      const j = Math.floor(Math.random() * (i + 1));
      [ids[i], ids[j]] = [ids[j], ids[i]];
    }
    const chosen = ids.slice(0, Math.max(1, randomCount.value));
    selection.ids = new Set(chosen);
    success.value = chosen.length < randomCount.value
      ? `Nur ${chosen.length} geeignete Fragen vorhanden, alle ausgewählt.`
      : `${chosen.length} zufällige Fragen ausgewählt, ohne widersprüchliche, ähnliche und fehlerhafte.`;
  }, "Zufallsauswahl fehlgeschlagen.");
}

function exportSelected() {
  return guarded(async () => {
    const name = filename.value.trim() || "moodle_fragen";
    const blob = await api.exportXml(selectedIds.value, name, prefix.value.trim());
    downloadBlob(blob, name.endsWith(".xml") ? name : `${name}.xml`);
    success.value = `${selection.ids.size} Frage(n) als „${name}.xml“ exportiert. In Moodle: Fragensammlung → Importieren → Moodle-XML.`;
    setSelected(selectedIds.value, false);
    await load();
  }, "Export fehlgeschlagen.");
}
</script>

<template>
  <div class="page-head">
    <h1>Fragenbank</h1>
    <p>Suchen Sie in allen Fragen, Antworten, Kategorien und Dateinamen. Auswählen und als Moodle-XML exportieren.</p>
  </div>

  <div class="card">
    <input id="q" v-model="search" class="searchbox" autofocus aria-label="Suche"
           placeholder="Suchen: Fragetext, Antwort, Kategorie, Dateiname … (alle Wörter müssen vorkommen)" />

    <div class="filters" style="margin-top: 0.75rem">
      <div>
        <label for="fach">Fach</label>
        <select id="fach" :value="query.fach ?? ''" @change="setQuery({ fach: ($event.target as HTMLSelectElement).value, category: undefined })">
          <option value="">Alle Fächer</option>
          <option v-for="f in fachOptions" :key="f.value" :value="f.value">{{ f.value }} ({{ f.count }})</option>
        </select>
      </div>
      <div>
        <label for="cat">Kategorie</label>
        <select id="cat" :value="query.category ?? ''" @change="setQuery({ category: ($event.target as HTMLSelectElement).value })">
          <option value="">Alle Kategorien</option>
          <option v-for="c in categoryOptions" :key="c.value" :value="c.value">{{ c.value }} ({{ c.count }})</option>
        </select>
      </div>
      <div>
        <label for="file">Datei</label>
        <select id="file" :value="query.file ?? ''" @change="setQuery({ file: ($event.target as HTMLSelectElement).value })">
          <option value="">Alle Dateien</option>
          <option v-for="f in fileOptions" :key="f.id" :value="f.id">{{ f.value }} ({{ f.count }})</option>
        </select>
      </div>
      <div>
        <label for="type">Fragetyp</label>
        <select id="type" :value="query.type ?? ''" @change="setQuery({ type: ($event.target as HTMLSelectElement).value })">
          <option value="">Alle Typen</option>
          <option v-for="t in typeOptions" :key="t.value" :value="t.value">{{ typeLabel(t.value) }} ({{ t.count }})</option>
        </select>
      </div>
      <div>
        <label for="flag">Hinweise</label>
        <select id="flag" :value="query.flag ?? ''" @change="setQuery({ flag: ($event.target as HTMLSelectElement).value })">
          <option value="">Alle Fragen</option>
          <option v-for="(label, key) in FLAG_LABELS" :key="key" :value="key">{{ label }}</option>
        </select>
      </div>
      <div>
        <label for="exported" title="Zählt nur Exporte aus dieser App (siehe Verlauf), nicht Tests in Moodle.">Aus der App exportiert?</label>
        <select id="exported" :value="query.exported ?? ''" title="Zählt nur Exporte aus dieser App (siehe Verlauf), nicht Tests in Moodle."
                @change="setQuery({ exported: ($event.target as HTMLSelectElement).value })">
          <option value="">Egal</option>
          <option value="no">Nein, noch nie</option>
          <option value="yes">Ja, schon einmal</option>
        </select>
      </div>
      <div>
        <label for="sort">Sortierung</label>
        <select id="sort" :value="query.sort" @change="setQuery({ sort: ($event.target as HTMLSelectElement).value })">
          <option v-for="(label, key) in SORT_LABELS" :key="key" :value="key">{{ label }}</option>
        </select>
      </div>
    </div>

    <div v-if="activeFilters.length || query.q" class="chips" style="margin-top: 0.75rem">
      <span v-if="query.q" class="chip">Suche: <strong>{{ query.q }}</strong>
        <button class="ghost small" aria-label="Suche löschen" @click="search = ''">×</button></span>
      <span v-for="f in activeFilters" :key="f.key" class="chip">{{ f.label }}
        <button class="ghost small" :aria-label="`${f.label} entfernen`" @click="setQuery({ [f.key]: undefined })">×</button></span>
      <button class="ghost small" @click="resetFilters">Alles zurücksetzen</button>
    </div>
  </div>

  <div v-if="error" class="notice error">{{ error }}</div>
  <div v-if="success" class="notice success">{{ success }}</div>

  <div class="toolbar">
    <span class="muted">
      <template v-if="!result">Lädt…</template>
      <template v-else-if="result.total === 0">Keine Treffer</template>
      <template v-else>Zeige {{ formatNumber(first) }}–{{ formatNumber(last) }} von <strong>{{ formatNumber(result.total) }}</strong> Frage(n)</template>
    </span>
    <span class="spacer" />
    <template v-if="result && result.total">
      <button class="secondary small" :disabled="!selectableOnPage.length" @click="toggleThisPage">
        {{ pageAllSelected ? "Seite abwählen" : "Diese Seite auswählen" }}
      </button>
      <button v-if="result.total > items.length" class="secondary small" :disabled="busy" @click="selectAllResults">
        Alle {{ formatNumber(result.total) }} Treffer auswählen
      </button>
      <span class="row" style="gap: 0.35rem">
        <button class="secondary small" :disabled="busy" @click="randomPick" title="Zufällig aus allen Treffern, ohne auffällige Fragen">Zufällig</button>
        <input v-model.number="randomCount" type="number" min="1" max="500" aria-label="Anzahl zufälliger Fragen" style="width: 70px; padding: 0.3rem" />
        <span class="muted">Fragen</span>
      </span>
    </template>
  </div>

  <div v-if="!loading && result && result.total === 0" class="card empty">
    <div class="icon">🔍</div>
    <p v-if="query.q || activeFilters.length">Keine Fragen für diese Suche. <button class="secondary small" @click="resetFilters">Filter zurücksetzen</button></p>
    <p v-else>Noch keine Fragen. <router-link to="/import">Jetzt Moodle-XML importieren →</router-link></p>
  </div>

  <div :style="{ opacity: loading ? 0.55 : 1, transition: 'opacity 0.15s' }">
    <div v-for="q in items" :key="q.id" class="card tight q-card">
      <input type="checkbox" :checked="selection.ids.has(q.id)" :disabled="q.status !== 'approved'"
             :title="q.status !== 'approved' ? 'Nur freigegebene Fragen können exportiert werden' : 'Für den Export auswählen'"
             @change="toggleSelected(q.id)" style="margin-top: 0.3rem" />
      <div>
        <div class="meta">
          <span class="q-title">
            <template v-for="(seg, i) in highlight(q.name || 'Ohne Namen', terms)" :key="i"><mark v-if="seg.hit">{{ seg.text }}</mark><template v-else>{{ seg.text }}</template></template>
          </span>
          <span class="badge neutral">{{ typeLabel(q.question_type) }}</span>
          <span v-if="q.ai_generated" class="badge violet">KI</span>
          <span v-if="q.status !== 'approved'" class="badge" :class="q.status">{{ q.status === "pending" ? "noch nicht freigegeben" : "abgelehnt" }}</span>
          <span v-for="f in q.flags" :key="f.label" class="badge" :class="f.kind">{{ f.label }}</span>
          <span v-if="terms.length && hits.get(q.id)?.length" class="muted">· Treffer in: {{ hits.get(q.id)!.join(", ") }}</span>
        </div>
        <div class="q-text">
          <template v-for="(seg, i) in highlight(body(q.id), terms)" :key="i"><mark v-if="seg.hit">{{ seg.text }}</mark><template v-else>{{ seg.text }}</template></template>
        </div>
        <div class="chips">
          <span class="chip" v-if="q.fach">📚 <strong>{{ q.fach }}</strong> / {{ q.category }}</span>
          <span v-for="o in q.origins" :key="o.file_id + (o.category ?? '')" class="chip" :title="o.category ?? ''">📄 {{ o.filename }}</span>
          <span v-if="!q.origins.length && q.ai_generated" class="chip">🤖 aus Vorlesungsmaterial generiert</span>
          <span v-for="e in q.exported_in" :key="e" class="chip export">⬆ exportiert in {{ e }}</span>
        </div>
        <button v-if="q.answers.length || isLong(q.id)" class="ghost small" style="margin-top: 0.35rem; padding-left: 0" @click="toggleExpanded(q.id)">
          {{ expanded.has(q.id) ? "Weniger anzeigen" : q.answers.length ? `Ganzen Text und ${q.answers.length} Antwort(en) anzeigen` : "Ganzen Text anzeigen" }}
        </button>
        <ul v-if="expanded.has(q.id)" class="answers-list">
          <li v-for="a in q.answers" :key="a.id" :class="{ correct: a.is_correct }">
            <template v-for="(seg, i) in highlight(answerText(a.text, q.question_type), terms)" :key="i"><mark v-if="seg.hit">{{ seg.text }}</mark><template v-else>{{ seg.text }}</template></template>
          </li>
        </ul>
      </div>
    </div>
  </div>

  <div v-if="result && result.pages > 1" class="pager">
    <button class="secondary small" :disabled="result.page <= 1" @click="goTo(1)">« Erste</button>
    <button class="secondary small" :disabled="result.page <= 1" @click="goTo(result.page - 1)">‹ Zurück</button>
    <span>Seite <strong>{{ result.page }}</strong> von {{ formatNumber(result.pages) }}</span>
    <button class="secondary small" :disabled="result.page >= result.pages" @click="goTo(result.page + 1)">Weiter ›</button>
    <button class="secondary small" :disabled="result.page >= result.pages" @click="goTo(result.pages)">Letzte »</button>
    <select :value="query.page_size" aria-label="Fragen pro Seite" style="width: auto" @change="setQuery({ size: ($event.target as HTMLSelectElement).value })">
      <option v-for="n in [25, 50, 100, 200]" :key="n" :value="n">{{ n }} pro Seite</option>
    </select>
  </div>

  <div v-if="selection.ids.size" class="selection-bar">
    <strong>{{ formatNumber(selection.ids.size) }} ausgewählt</strong>
    <button class="ghost small" style="color: #fff" @click="setSelected(selectedIds, false)">Auswahl leeren</button>
    <span class="grow" />
    <input v-model="prefix" placeholder="Kategorie-Ordner (optional), z. B. Prüfung WS 25/26" aria-label="Kategorie-Ordner"
           title="Legt alle Fragen in eigene Kategorien unter diesem Namen, damit sie sich in Moodle nicht mit den Originalen vermischen" style="width: 330px" />
    <input v-model="filename" placeholder="Dateiname" aria-label="Dateiname" />
    <button :disabled="busy" @click="exportSelected">
      <span v-if="busy" class="spinner" /> Als Moodle-XML exportieren
    </button>
    <div v-for="w in selectionWarnings" :key="w" class="warn">⚠ {{ w }}</div>
  </div>
</template>
