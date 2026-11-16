<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { api, ApiError, type BankOverview, type PlanResult } from "../api";
import { downloadBlob, formatNumber, formatVariants, LEVEL_BADGE, LEVEL_TEXT } from "../bank";

const SEP = "\u0001";
interface Row { key: string; count: number; percent: number }

const overview = ref<BankOverview | null>(null);
const rows = ref<Row[]>([{ key: "", count: 4, percent: 100 }]);
const mode = ref<"count" | "percent">("count");
const total = ref(20);
const seedInput = ref<number | undefined>(undefined);
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
  if (all.length) rows.value = [{ key: all[0].key, count: 4, percent: 100 }];
});

watch([rows, students, onlyUnused, mode, total, seedInput], () => { if (plan.value) stale.value = true; }, { deep: true });

function parse(key: string): { fach: string | null; category: string } {
  const [fach, category] = key.split(SEP);
  return { fach: fach === "Ohne Fach" ? null : fach, category };
}
const slots = computed(() => rows.value.filter((r) => r.key).map((r) =>
  mode.value === "percent" ? { ...parse(r.key), percent: r.percent } : { ...parse(r.key), count: r.count }));
const percentSum = computed(() => Math.round(rows.value.filter((r) => r.key).reduce((n, r) => n + (Number(r.percent) || 0), 0) * 100) / 100);
const extra = computed(() => (mode.value === "percent" ? { total: total.value } : {}));
const chosen = computed(() => new Set(rows.value.map((r) => r.key)));

function addRow() {
  rows.value.push({ key: "", count: 2, percent: 0 });
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
  if (mode.value === "percent" && percentSum.value !== 100) {
    error.value = `Die Prozentwerte ergeben ${percentSum.value} %. Sie müssen zusammen genau 100 % ergeben.`;
    return;
  }
  busy.value = true;
  try {
    plan.value = await api.plan({ slots: slots.value, students: students.value, only_unused: onlyUnused.value, seed: seedInput.value || undefined, ...extra.value });
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
      slots: slots.value, students: students.value, seed: plan.value.seed, only_unused: onlyUnused.value, ...extra.value,
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
    <div class="tabs" role="group" aria-label="Verteilung festlegen">
      <button :class="{ active: mode === 'count' }" @click="mode = 'count'">Anzahl je Kategorie</button>
      <button :class="{ active: mode === 'percent' }" @click="mode = 'percent'">Prozentuale Verteilung</button>
    </div>
    <div v-if="mode === 'percent'" style="max-width: 320px; margin-bottom: 0.5rem">
      <label for="total">Fragen pro Person insgesamt</label>
      <input id="total" v-model.number="total" type="number" min="1" max="100" />
      <div class="hint">Die Prozente werden auf ganze Fragen gerundet (größter Rest zuerst), sodass die Summe stimmt. Die tatsächliche Anzahl sehen Sie unten im Plan.</div>
    </div>
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
      <div v-if="mode === 'count'">
        <label :for="`n${i}`">Fragen pro Person</label>
        <input :id="`n${i}`" v-model.number="row.count" type="number" min="1" max="50" />
      </div>
      <div v-else>
        <label :for="`p${i}`">Anteil in %</label>
        <input :id="`p${i}`" v-model.number="row.percent" type="number" min="1" max="100" step="any" />
      </div>
      <button class="ghost" :aria-label="`Kategorie ${i + 1} entfernen`" @click="removeRow(i)">Entfernen</button>
    </div>
    <button class="secondary small" @click="addRow">+ Weitere Kategorie</button>
    <p v-if="mode === 'percent'" :class="percentSum === 100 ? 'muted' : 'notice warn'" role="status" style="margin-bottom: 0">
      Summe: <strong>{{ percentSum }} %</strong><template v-if="percentSum !== 100"> (muss 100 % sein)</template>
    </p>

    <div class="grid-2" style="margin-top: 1rem">
      <div>
        <label for="students">Wie viele Studierende schreiben den Test?</label>
        <input id="students" v-model.number="students" type="number" min="1" max="2000" />
      </div>
      <div>
        <label for="seed">Startwert (optional)</label>
        <input id="seed" v-model.number="seedInput" type="number" min="1" placeholder="leer = zufällig" />
        <div class="hint">Derselbe Startwert ergibt dieselbe Simulation und denselben Verteilungsplan, so lässt sich ein Ergebnis später wiederholen.</div>
      </div>
      <div>
        <label style="margin-top: 1.9rem; display: flex; gap: 0.5rem; align-items: center; font-weight: 400">
          <input v-model="onlyUnused" type="checkbox" />
          Nur Fragen, die noch nie exportiert wurden
        </label>
      </div>
    </div>

    <div v-if="error" class="notice error" role="alert">{{ error }}</div>
    <div class="row" style="margin-top: 1rem">
      <button :disabled="busy" @click="run"><span v-if="busy" class="spinner" /> Plan berechnen</button>
    </div>
  </div>

  <template v-if="plan">
    <div v-if="stale" class="notice warn" role="status">Die Eingaben wurden geändert. Bitte den Plan neu berechnen.</div>

    <div class="notice" :class="plan.ok ? 'success' : 'error'" role="status">
      <template v-if="plan.ok">
        <strong>Der Plan ist möglich.</strong> Jede Person bekommt {{ plan.per_paper }} Fragen
        aus {{ plan.slots.length }} Kategorie(n). Es gibt {{ formatVariants(plan.variants_log10 ?? 0) }} verschiedene Fragensets.
      </template>
      <template v-else>
        <strong>Der Plan funktioniert so nicht:</strong> In mindestens einer Kategorie gibt es nicht genug brauchbare Fragen.
      </template>
    </div>
    <div v-for="w in plan.warnings" :key="w" class="notice warn" role="status">⚠ {{ w }}</div>

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
        <p class="muted" style="margin: 0.4rem 0 0">
          Abdeckung: <strong>{{ s.coverage_percent }} %</strong> der empfohlenen Poolgröße<template v-if="s.missing_for_recommended">, es fehlen noch <strong>{{ s.missing_for_recommended }}</strong> Frage(n)</template><template v-else>, ausreichend</template>.
        </p>
        <div class="bar" style="margin-top: 0.3rem" :title="`${s.pool_size} von empfohlen ${s.recommended_min}`">
          <span :style="{ width: s.coverage_percent + '%',
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

    <div v-if="plan.ok && plan.random && plan.balanced" class="card">
      <h2>Verteilung der Überschneidungen</h2>
      <p class="muted" style="margin-top: 0">Wie viele Personenpaare (aus {{ formatNumber(plan.random.pairs_compared) }} verglichenen) haben genau so viele gleiche Fragen?</p>
      <div v-for="(label, key) in { random: 'Zufällig (wie Moodle)', balanced: 'Feste Verteilung' }" :key="key" style="margin-bottom: 0.8rem">
        <strong>{{ label }}</strong>
        <div v-for="h in plan[key as 'random' | 'balanced']!.overlap_histogram" :key="h.shared" class="hbar">
          <span style="width: 7rem">{{ h.shared }} gleiche</span>
          <span class="track"><span class="fill" :style="{ width: (100 * h.pairs / plan[key as 'random' | 'balanced']!.pairs_compared) + '%' }" /></span>
          <span style="width: 6rem; text-align: right">{{ formatNumber(h.pairs) }}</span>
        </div>
      </div>
    </div>

    <div v-if="plan.statements.length" class="card">
      <h2>Was ist berechnet, simuliert, nicht garantierbar?</h2>
      <div v-for="st in plan.statements" :key="st.text" class="statement" :class="st.kind">
        <strong>{{ { calculated: "Berechnet", simulated: "Simuliert", not_guaranteed: "Nicht garantierbar" }[st.kind] }}:</strong> {{ st.text }}
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
        <li>Moodle zieht dann für jede Person zufällig. Eine Frage kommt in einem Versuch nie doppelt vor, aber Überschneidungen zwischen Personen sind möglich (siehe oben: „Nicht garantierbar“).</li>
      </ol>
      <p class="muted">
        Der Verteilungsplan (CSV) ist nur nötig, wenn Sie die Fragen fest zuteilen wollen, z. B. für gedruckte Tests.
        Der Plan lässt sich mit demselben Startwert ({{ plan.seed }}) jederzeit gleich wieder erzeugen.
      </p>
    </div>
  </template>
</template>
