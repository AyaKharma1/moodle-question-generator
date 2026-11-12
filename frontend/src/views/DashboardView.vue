<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api, type BankOverview } from "../api";
import { checkRandomDraw, type DrawLevel } from "../bank";

const overview = ref<BankOverview | null>(null);
const loading = ref(true);
const perTest = ref(4);

onMounted(async () => {
  try {
    overview.value = await api.overview();
  } finally {
    loading.value = false;
  }
});

const levelText: Record<DrawLevel, string> = {
  impossible: "zu wenige Fragen",
  small: "zu klein",
  tight: "knapp",
  good: "gut",
};
const levelBadge: Record<DrawLevel, string> = {
  impossible: "danger",
  small: "danger",
  tight: "warn",
  good: "ok",
};
</script>

<template>
  <div class="page-head">
    <h1>Übersicht</h1>
    <p>Alle Fragen aus Ihren Moodle-Exporten an einem Ort: nach Fach und Kategorie sortiert, mit Herkunft und ohne Duplikate.</p>
  </div>

  <div v-if="loading" class="muted">Lädt…</div>

  <div v-else-if="!overview || overview.totals.questions === 0" class="card empty">
    <div class="icon">📥</div>
    <h2>Noch keine Fragen in der Fragenbank</h2>
    <p>
      Exportieren Sie Ihre Fragensammlung in Moodle als <strong>Moodle-XML</strong> und importieren Sie
      die Dateien hier, auch mehrere auf einmal und aus verschiedenen Fächern.
    </p>
    <router-link to="/import" class="button">XML-Dateien importieren</router-link>
  </div>

  <template v-else>
    <div class="stats">
      <router-link to="/bank" class="stat"><div class="value">{{ overview.totals.questions }}</div><div class="label">Fragen</div></router-link>
      <router-link to="/verlauf" class="stat"><div class="value">{{ overview.totals.files }}</div><div class="label">Importierte Dateien</div></router-link>
      <div class="stat"><div class="value">{{ overview.totals.fachs }}</div><div class="label">Fächer · {{ overview.totals.categories }} Kategorien</div></div>
      <router-link to="/pruefung" class="stat" :class="overview.totals.conflicts ? 'danger' : 'ok'">
        <div class="value">{{ overview.totals.conflicts }}</div><div class="label">Widersprüche</div>
      </router-link>
      <router-link to="/pruefung" class="stat" :class="overview.totals.similar ? 'violet' : 'ok'">
        <div class="value">{{ overview.totals.similar }}</div><div class="label">Ähnliche Fragen</div>
      </router-link>
      <router-link to="/pruefung" class="stat" :class="overview.totals.issues ? 'warn' : 'ok'">
        <div class="value">{{ overview.totals.issues }}</div><div class="label">Fehlerhafte Fragen</div>
      </router-link>
    </div>

    <div v-if="overview.totals.duplicates" class="notice info">
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
            📚 {{ f.fach }}
          </router-link>
          <span class="badge neutral">{{ f.count }} Fragen</span>
        </div>
        <div v-for="c in f.categories" :key="c.name" class="tree-cat">
          <router-link :to="{ name: 'bank', query: { fach: f.fach, category: c.name } }">📁 {{ c.name }}</router-link>
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
