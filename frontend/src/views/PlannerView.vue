<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { api, ApiError, type BankOverview, type PlanResult } from "../api";
import { downloadBlob, formatNumber, formatVariants, LEVEL_BADGE, LEVEL_TEXT } from "../bank";

const SEP = "\u0001";
interface Row { key: string; count: number }

const overview = ref<BankOverview | null>(null);
const rows = ref<Row[]>([{ key: "", count: 4 }]);
const students = ref(100);
const onlyUnused = ref(false);
const prefix = ref("Prüfung");
const filename = ref("pruefung_pool");

const plan = ref<PlanResult | null>(null);
const stale = ref(false);
const busy = ref(false);
const error = ref("");

onMounted(async () => {
  overview.value = await api.overview();
  // start with the biggest category so the first plan is meaningful
  const all = (overview.value.tree ?? []).flatMap((f) => f.categories.map((c) => ({ key: f.fach + SEP + c.name, n: c.count })));
  all.sort((a, b) => b.n - a.n);
  if (all.length) rows.value = [{ key: all[0].key, count: 4 }];
});

watch([rows, students, onlyUnused], () => { if (plan.value) stale.value = true; }, { deep: true });

function parse(key: string): { fach: string | null; category: string } {
  const [fach, category] = key.split(SEP);
  return { fach: fach === "Ohne Fach" ? null : fach, category };
}
const slots = computed(() => rows.value.filter((r) => r.key).map((r) => ({ ...parse(r.key), count: r.count })));
const chosen = computed(() => new Set(rows.value.map((r) => r.key)));

function addRow() {
  rows.value.push({ key: "", count: 2 });
}
function removeRow(i: number) {
  rows.value.splice(i, 1);
  if (rows.value.length === 0) addRow();
}

async function run() {
  error.value = "";
  if (slots.value.length === 0) {
    error.value = "Bitte mindestens eine Kategorie wählen.";
    return;
  }
  busy.value = true;
  try {
    plan.value = await api.plan({ slots: slots.value, students: students.value, only_unused: onlyUnused.value });
    stale.value = false;
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Planen fehlgeschlagen.";
  } finally {
    busy.value = false;
  }
}

async function downloadPool() {
  if (!plan.value) return;
  error.value = "";
  busy.value = true;
  try {
    const name = filename.value.trim() || "pruefung_pool";
    downloadBlob(await api.exportXml(plan.value.pool_ids, name, prefix.value.trim()), name.endsWith(".xml") ? name : `${name}.xml`);
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Export fehlgeschlagen.";
  } finally {
    busy.value = false;
  }
}

async function downloadCsv() {
  if (!plan.value) return;
  error.value = "";
  busy.value = true;
  try {
    const blob = await api.planCsv({
      slots: slots.value, students: students.value, seed: plan.value.seed, only_unused: onlyUnused.value,
    });
    downloadBlob(blob, "verteilungsplan.csv");
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "CSV fehlgeschlagen.";
  } finally {
    busy.value = false;
  }
}

const reasons = computed(() => (plan.value?.slots ?? []).reduce((n, s) => n + s.removed.length, 0));
</script>

<template>
  <div class="page-head">
    <h1>Testplaner</h1>
    <p>
      Jede Person soll andere Fragen bekommen, und niemand dieselbe oder eine fast gleiche Frage zweimal.
      Moodle zieht die Fragen zufällig aus einer Kategorie. Hier bauen und prüfen Sie den Fragenpool, aus dem gezogen wird.
    </p>
  </div>

  <div class="card">
    <h2>1 · Was soll der Test enthalten?</h2>
    <div v-for="(row, i) in rows" :key="i" class="plan-row">
      <div>
        <label :for="`cat${i}`">Kategorie</label>
        <select :id="`cat${i}`" v-model="row.key">
          <option value="" disabled>Kategorie wählen…</option>
          <optgroup v-for="f in overview?.tree ?? []" :key="f.fach" :label="f.fach">
            <option v-for="c in f.categories" :key="c.name" :value="f.fach + SEP + c.name"
                    :disabled="chosen.has(f.fach + SEP + c.name) && row.key !== f.fach + SEP + c.name">
              {{ c.name }} ({{ c.count }} Fragen)
            </option>
          </optgroup>
        </select>
      </div>
      <div>
        <label :for="`n${i}`">Fragen pro Person</label>
        <input :id="`n${i}`" v-model.number="row.count" type="number" min="1" max="50" />
      </div>
      <button class="ghost" :aria-label="`Kategorie ${i + 1} entfernen`" @click="removeRow(i)">Entfernen</button>
    </div>
    <button class="secondary small" @click="addRow">+ Weitere Kategorie</button>

    <div class="grid-2" style="margin-top: 1rem">
      <div>
        <label for="students">Wie viele Studierende schreiben den Test?</label>
        <input id="students" v-model.number="students" type="number" min="1" max="2000" />
      </div>
      <div>
        <label style="margin-top: 1.9rem; display: flex; gap: 0.5rem; align-items: center; font-weight: 400">
          <input v-model="onlyUnused" type="checkbox" />
          Nur Fragen, die noch in keinem Export waren
        </label>
      </div>
    </div>

    <div v-if="error" class="notice error">{{ error }}</div>
    <div class="row" style="margin-top: 1rem">
      <button :disabled="busy" @click="run"><span v-if="busy" class="spinner" /> Plan berechnen</button>
    </div>
  </div>

  <template v-if="plan">
    <div v-if="stale" class="notice warn">Die Eingaben wurden geändert. Bitte den Plan neu berechnen.</div>

    <div class="notice" :class="plan.ok ? 'success' : 'error'">
      <template v-if="plan.ok">
        <strong>Der Plan ist möglich.</strong> Jede Person bekommt {{ plan.per_paper }} Fragen
        aus {{ plan.slots.length }} Kategorie(n). Es gibt {{ formatVariants(plan.variants_log10 ?? 0) }} verschiedene Fragensets.
      </template>
      <template v-else>
        <strong>Der Plan funktioniert so nicht:</strong> In mindestens einer Kategorie gibt es nicht genug brauchbare Fragen.
      </template>
    </div>
    <div v-for="w in plan.warnings" :key="w" class="notice warn">⚠ {{ w }}</div>

    <div class="card">
      <h2>2 · Fragenpool je Kategorie</h2>
      <div v-for="s in plan.slots" :key="s.label" class="card tight">
        <div class="card-head" style="margin-bottom: 0.4rem">
          <strong>📁 {{ s.label }}</strong>
          <span class="badge" :class="LEVEL_BADGE[s.level]">{{ LEVEL_TEXT[s.level] }}</span>
        </div>
        <div class="chips">
          <span class="chip"><strong>{{ s.pool_size }}</strong> brauchbare Fragen im Pool<template v-if="s.pool_before !== s.pool_size"> (von {{ s.pool_before }})</template></span>
          <span class="chip"><strong>{{ s.count }}</strong> pro Person</span>
          <span v-if="s.shared_expected !== null" class="chip">zwei Personen haben im Schnitt <strong>{{ formatNumber(s.shared_expected) }}</strong> gleiche</span>
          <span class="chip">empfohlen: mindestens <strong>{{ s.recommended_min }}</strong></span>
        </div>
        <div class="bar" style="margin-top: 0.5rem" :title="`${s.pool_size} von empfohlen ${s.recommended_min}`">
          <span :style="{ width: Math.min(100, (s.pool_size / s.recommended_min) * 100) + '%',
                          background: s.level === 'good' ? 'var(--ok)' : s.level === 'tight' ? 'var(--warn)' : 'var(--danger)' }" />
        </div>
        <details v-if="s.removed.length" style="margin-top: 0.5rem">
          <summary class="muted">{{ s.removed.length }} Frage(n) nicht im Pool, und warum</summary>
          <ul style="margin: 0.4rem 0 0; padding-left: 1.1rem">
            <li v-for="r in s.removed" :key="r.id"><strong>{{ r.name }}</strong> <span class="muted">· {{ r.reason }}</span></li>
          </ul>
        </details>
      </div>
      <p v-if="reasons" class="muted" style="margin-bottom: 0">
        Aussortiert wird, was in einem Test nicht ungeprüft landen soll: reine Beschreibungstexte, widersprüchliche und fehlerhafte Fragen
        sowie eine von zwei fast gleichen Fragen (auch zwischen verschiedenen Kategorien).
      </p>
    </div>

    <div v-if="plan.ok && plan.random && plan.balanced" class="card">
      <h2>3 · Simulation mit {{ formatNumber(plan.students) }} Studierenden</h2>
      <table class="list compare-table">
        <thead><tr><th /><th>Zufällig<br /><span class="muted" style="font-weight: 400; text-transform: none">(so arbeitet Moodle)</span></th>
          <th>Ausgewogener Plan<br /><span class="muted" style="font-weight: 400; text-transform: none">(feste Verteilung, CSV)</span></th></tr></thead>
        <tbody>
          <tr><td>Gleiche Fragen bei zwei Personen, Ø</td><td>{{ formatNumber(plan.random.avg_overlap) }}</td><td>{{ formatNumber(plan.balanced.avg_overlap) }}</td></tr>
          <tr><td>Gleiche Fragen bei zwei Personen, höchstens</td><td>{{ plan.random.max_overlap }}</td><td>{{ plan.balanced.max_overlap }}</td></tr>
          <tr><td>Verschiedene Fragensets</td><td>{{ formatNumber(plan.random.unique_papers) }} von {{ formatNumber(plan.students) }}</td>
            <td>{{ formatNumber(plan.balanced.unique_papers) }} von {{ formatNumber(plan.students) }}</td></tr>
          <tr><td>Personen mit exakt gleichem Fragenset wie jemand anderes</td><td>{{ formatNumber(plan.random.students_with_identical_paper) }}</td>
            <td>{{ formatNumber(plan.balanced.students_with_identical_paper) }}</td></tr>
          <tr><td>Wie oft wird eine Frage verwendet (min–max)</td><td>{{ plan.random.usage_min }}–{{ plan.random.usage_max }}</td>
            <td>{{ plan.balanced.usage_min }}–{{ plan.balanced.usage_max }}</td></tr>
        </tbody>
      </table>
      <p class="muted">
        Wie viele Fragen zwei Personen gemeinsam haben, hängt nur von der Poolgröße ab: je größer der Pool, desto weniger.
        Der ausgewogene Plan verwendet jede Frage gleich oft und gibt niemandem dasselbe Set, solange genug verschiedene Sets möglich sind.
      </p>

      <h3 style="margin-top: 1rem">Beispiel: die ersten Fragensets</h3>
      <div v-for="p in plan.sample_papers" :key="p.student" class="chips" style="margin-bottom: 0.4rem">
        <strong style="min-width: 5.5rem">Person {{ p.student }}</strong>
        <span v-for="q in p.questions" :key="q.id" class="chip" :title="q.category">{{ q.name }}</span>
      </div>
    </div>

    <div v-if="plan.ok" class="card">
      <h2>4 · Weiter mit dem Plan</h2>
      <div class="grid-2">
        <div>
          <label for="prefix">Ordner in Moodle (Kategorie-Präfix)</label>
          <input id="prefix" v-model="prefix" />
          <div class="hint">Der Pool kommt in eigene Kategorien unter diesem Ordner. So vermischt er sich beim Import nicht mit den Originalfragen.</div>
        </div>
        <div>
          <label for="fn">Dateiname</label>
          <input id="fn" v-model="filename" />
        </div>
      </div>
      <div class="row" style="margin-top: 1rem">
        <button :disabled="busy || stale" @click="downloadPool">⬇ Pool als Moodle-XML</button>
        <button class="secondary" :disabled="busy || stale" @click="downloadCsv">⬇ Verteilungsplan als CSV</button>
      </div>

      <h3 style="margin-top: 1.25rem">So stellen Sie es in Moodle ein</h3>
      <ol style="margin: 0.25rem 0 0; padding-left: 1.2rem">
        <li>Pool-Datei importieren: Fragensammlung → <em>Importieren</em> → Moodle-XML.</li>
        <li>Im Test: <em>Fragen → Hinzufügen → Eine zufällige Frage</em>.</li>
        <li v-for="s in plan.slots" :key="s.label">
          Kategorie <strong>„{{ s.category }}“</strong> im Ordner „{{ prefix || "…" }}“ wählen, <strong>{{ s.count }}</strong> Frage(n) hinzufügen.
        </li>
        <li>Jede Person bekommt dann andere zufällige Fragen, und eine Frage kommt in einem Versuch nie doppelt vor.</li>
      </ol>
      <p class="muted">
        Der Verteilungsplan (CSV) ist nur nötig, wenn Sie die Fragen fest zuteilen wollen, z. B. für gedruckte Tests.
        Der Plan lässt sich mit demselben Startwert ({{ plan.seed }}) jederzeit gleich wieder erzeugen.
      </p>
    </div>
  </template>
</template>
