<script setup lang="ts">
import Icon from "../components/Icon.vue";
import { computed, onMounted, ref } from "vue";
import { api, ApiError, type BankOverview, type ExportRecord, type ImportFile } from "../api";
import { demoState, refreshDemo } from "../demo";
import { checkRandomDraw, formatDate, LEVEL_BADGE as levelBadge, LEVEL_TEXT as levelText } from "../bank";

const overview = ref<BankOverview | null>(null);
const loading = ref(true);
const perTest = ref(4);
const files = ref<ImportFile[]>([]);
const exports = ref<ExportRecord[]>([]);
const error = ref("");

async function load() {
  try {
    [overview.value, files.value, exports.value] = await Promise.all([api.overview(), api.listImportFiles(), api.exportHistory()]);
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Die Übersicht konnte nicht geladen werden.";
  } finally {
    loading.value = false;
  }
}
onMounted(load);

async function loadDemo() {
  error.value = "";
  loading.value = true;
  try {
    await api.loadDemo();
    await refreshDemo();
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Die Demo-Daten konnten nicht geladen werden.";
  }
  await load();
}

// What to do next, derived only from real numbers.
const tasks = computed(() => {
  const o = overview.value;
  if (!o) return [];
  const q = o.quality;
  const out: { text: string; to: object | string; level: string }[] = [];
  if (q.open_conflicts) out.push({ level: "danger", to: "/pruefung", text: `${q.open_conflicts} Widerspruch/Widersprüche klären: gleiche Frage, andere richtige Antwort.` });
  if (q.open.critical) out.push({ level: "danger", to: "/pruefung", text: `${q.open.critical} Fragen mit kritischem Hinweis ansehen (z. B. fehlende richtige Antwort, fehlendes Bild).` });
  if (q.open.review) out.push({ level: "warn", to: "/pruefung", text: `${q.open.review} Hinweise zum Überprüfen ansehen.` });
  if (!exports.value.length) out.push({ level: "info", to: "/bank", text: "Fragen auswählen und noch vor dem ersten Export die Vorschau ansehen." });
  return out;
});
const lastImport = computed(() => files.value[0]);
const lastExport = computed(() => exports.value[0]);

</script>

<template>
  <div class="page-head">
    <h1>Übersicht</h1>
    <p>Alle Fragen aus Ihren Moodle-Exporten an einem Ort: nach Fach und Kategorie sortiert, mit Herkunft und ohne Duplikate.</p>
  </div>

  <div v-if="loading" class="muted" role="status"><span class="spinner" /> Lädt…</div>
  <div v-if="error" class="notice error" role="alert">{{ error }}</div>

  <div v-else-if="!overview || overview.totals.questions === 0" class="card empty">
    <div class="icon"><Icon name="inbox" /></div>
    <h2>Noch keine Fragen in der Fragenbank</h2>
    <p>
      Exportieren Sie Ihre Fragensammlung in Moodle als <strong>Moodle-XML</strong> und importieren Sie
      die Dateien hier, auch mehrere auf einmal und aus verschiedenen Fächern.
    </p>
    <div class="row" style="justify-content: center">
      <router-link to="/import" class="button">XML-Dateien importieren</router-link>
      <button v-if="!demoState.loaded" class="secondary" @click="loadDemo">Mit Demo-Daten ausprobieren</button>
    </div>
    <p class="muted">Die Demo-Daten sind vollständig erfundene Fragen (Datenbanksysteme), klar gekennzeichnet und jederzeit entfernbar.</p>
  </div>

  <template v-else>
    <div class="stats">
      <router-link to="/bank" class="stat"><div class="value">{{ overview.totals.questions }}</div><div class="label">Fragen</div></router-link>
      <router-link to="/verlauf" class="stat"><div class="value">{{ overview.totals.files }}</div><div class="label">Importierte Dateien</div></router-link>
      <div class="stat"><div class="value">{{ overview.totals.fachs }}</div><div class="label">Fächer · {{ overview.totals.categories }} Kategorien</div></div>
      <router-link to="/pruefung" class="stat" :class="overview.quality.open.critical ? 'danger' : 'ok'">
        <div class="value">{{ overview.quality.open.critical }}</div><div class="label"><Icon name="critical" /> Kritisch (offen)</div>
      </router-link>
      <router-link to="/pruefung" class="stat" :class="overview.quality.open.review ? 'warn' : 'ok'">
        <div class="value">{{ overview.quality.open.review }}</div><div class="label"><Icon name="review" /> Überprüfen (offen)</div>
      </router-link>
      <router-link to="/pruefung" class="stat">
        <div class="value">{{ overview.quality.open.info }}</div><div class="label"><Icon name="info" /> Information</div>
      </router-link>
    </div>

    <div class="card">
      <h2>Nächste Schritte</h2>
      <p v-if="!tasks.length" class="notice success" role="status" style="margin: 0">
        Keine offenen kritischen Hinweise. Sie können Fragen auswählen und einen Test planen.
      </p>
      <ul v-else style="margin: 0; padding-left: 1.1rem">
        <li v-for="t in tasks" :key="t.text"><router-link :to="t.to">{{ t.text }}</router-link></li>
      </ul>
      <p class="muted" style="margin-bottom: 0">
        <template v-if="lastImport">Letzter Import: {{ lastImport.filename }} ({{ formatDate(lastImport.created_at) }}).</template>
        <template v-if="lastExport"> Letzter Export: {{ lastExport.filename }} ({{ formatDate(lastExport.created_at) }}<template v-if="lastExport.note">, {{ lastExport.note }}</template>).</template>
        <template v-else> Noch nichts exportiert.</template>
      </p>
      <div class="row">
        <router-link to="/import" class="button secondary small">Importieren</router-link>
        <router-link to="/pruefung" class="button secondary small">Qualität prüfen</router-link>
        <router-link to="/bank" class="button secondary small">Fragen auswählen</router-link>
        <router-link to="/planer" class="button secondary small">Test planen</router-link>
      </div>
    </div>

    <router-link to="/planer" class="card cta">
      <span class="icon"><Icon name="target" /></span>
      <span>
        <strong>Test planen</strong><br />
        <span class="muted">Fairen Fragenpool bauen: möglichst wenig Überschneidung zwischen Personen, nichts doppelt oder fast gleich.</span>
      </span>
      <span class="button small">Planen →</span>
    </router-link>

    <div v-if="overview.totals.duplicates" class="notice info" role="status">
      {{ overview.totals.duplicates }} Frage(n) kommen in mehreren Dateien vor. Sie sind in der Fragenbank
      nur <strong>einmal</strong> gespeichert, die Herkunft aus allen Dateien bleibt erhalten.
    </div>

    <div class="card">
      <div class="card-head">
        <h2>Fächer und Kategorien</h2>
        <label class="row" style="margin: 0; font-weight: 600; gap: 0.5rem">
          Zufallsfragen pro Test und Kategorie:
          <input type="number" min="1" max="50" v-model.number="perTest" style="width: 80px" />
        </label>
      </div>
      <p class="muted" style="margin-top: 0">
        Moodle zieht in einem Test für jede Person zufällig Fragen aus einer Kategorie. Ist die Kategorie zu klein,
        bekommen viele Studierende dieselben Fragen. Die Spalte rechts zeigt, wie viele gleiche Fragen zwei
        Studierende im Durchschnitt haben.
      </p>

      <div v-for="f in overview.tree" :key="f.fach" class="tree-fach">
        <div class="head">
          <router-link :to="{ name: 'bank', query: { fach: f.fach } }" style="color: inherit; text-decoration: none">
            <Icon name="book" /> {{ f.fach }}
          </router-link>
          <span class="badge neutral">{{ f.count }} Fragen</span>
        </div>
        <div v-for="c in f.categories" :key="c.name" class="tree-cat">
          <router-link :to="{ name: 'bank', query: { fach: f.fach, category: c.name } }"><Icon name="folder" /> {{ c.name }}</router-link>
          <span class="muted">{{ c.count }} Fragen</span>
          <span>
            <span class="badge" :class="levelBadge[checkRandomDraw(c.count, perTest).level]">
              {{ levelText[checkRandomDraw(c.count, perTest).level] }}
            </span>
            <span v-if="checkRandomDraw(c.count, perTest).level !== 'impossible'" class="muted">
              · Ø {{ checkRandomDraw(c.count, perTest).sharedOnAverage }} gleiche
            </span>
          </span>
        </div>
      </div>
    </div>
  </template>

  <div class="card">
    <h2>So funktioniert es</h2>
    <div class="flow">
      <div class="step"><div class="n">1</div><strong>In Moodle exportieren</strong><span>Fragensammlung → Exportieren → Format „Moodle-XML“</span></div>
      <div class="step"><div class="n">2</div><strong>Hier importieren</strong><span>Beliebig viele Dateien, auch aus verschiedenen Fächern</span></div>
      <div class="step"><div class="n">3</div><strong>Prüfen und auswählen</strong><span>Duplikate, Widersprüche und Fehler werden automatisch gefunden</span></div>
      <div class="step"><div class="n">4</div><strong>Zurück nach Moodle</strong><span>Ausgewählte Fragen als saubere XML-Datei mit Kategorien</span></div>
    </div>
  </div>
</template>
