<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api, type BankAnalysis, type BriefQuestion } from "../api";
import { answerText, formatNumber, typeLabel } from "../bank";

type Tab = "conflicts" | "similar" | "exact" | "issues";

const analysis = ref<BankAnalysis | null>(null);
const loading = ref(true);
const tab = ref<Tab>("conflicts");

onMounted(async () => {
  try {
    analysis.value = await api.analysis();
    const a = analysis.value;
    // Open the most important tab that actually has findings.
    tab.value = a.counts.conflicts ? "conflicts" : a.counts.similar ? "similar"
      : a.counts.issues ? "issues" : a.counts.exact ? "exact" : "conflicts";
  } finally {
    loading.value = false;
  }
});

const tabs = computed(() => {
  const a = analysis.value;
  return [
    { key: "conflicts" as Tab, label: "Widersprüche", count: a?.counts.conflicts ?? 0 },
    { key: "similar" as Tab, label: "Ähnliche Fragen", count: a?.counts.similar ?? 0 },
    { key: "issues" as Tab, label: "Fehlerhafte Fragen", count: a?.counts.issues ?? 0 },
    { key: "exact" as Tab, label: "In mehreren Dateien", count: a?.counts.exact ?? 0 },
  ];
});

function where(q: BriefQuestion): string {
  return q.origins.map((o) => `${o.filename} (${o.category ?? "–"})`).join(", ") || "KI-generiert";
}

// "Zeige die ersten 300 von 5.376": the lists are cut on the server for big banks
const trimmed = computed(() => {
  const a = analysis.value;
  const shown = (n: number) => (a && n > a.limit ? `Zeige die ersten ${formatNumber(a.limit)} von ${formatNumber(n)}.` : "");
  return {
    conflicts: shown(a?.counts.conflicts ?? 0), similar: shown(a?.counts.similar ?? 0),
    issues: shown(a?.counts.issues ?? 0), exact: shown(a?.counts.exact ?? 0),
  };
});

function bankLink(q: BriefQuestion) {
  return { name: "bank", query: { q: q.name ?? q.text.slice(0, 40) } };
}
</script>

<template>
  <div class="page-head">
    <h1>Qualität der Fragenbank</h1>
    <p>Probleme, die automatisch gefunden wurden, bevor Fragen in einem Test landen.</p>
  </div>

  <div v-if="loading" class="muted">Lädt…</div>
  <template v-else-if="analysis">
    <div class="tabs">
      <button v-for="t in tabs" :key="t.key" :class="{ active: tab === t.key }" @click="tab = t.key">
        {{ t.label }} <span class="badge" :class="t.count ? 'neutral' : 'ok'">{{ t.count }}</span>
      </button>
    </div>

    <!-- contradictions -->
    <template v-if="tab === 'conflicts'">
      <p class="muted">
        Dieselbe Frage steht in verschiedenen Dateien, aber mit <strong>anderen richtigen Antworten</strong>.
        Meist wurde die Frage in einer Datei korrigiert und in der anderen nicht. Bitte in Moodle klären, welche Version gilt.
      </p>
      <p v-if="trimmed.conflicts" class="notice info">{{ trimmed.conflicts }} Mit der Fragenbank-Suche und ihren Filtern finden Sie jede einzelne.</p>
      <p v-if="!analysis.conflicts.length" class="notice success">Keine Widersprüche gefunden. ✓</p>
      <div v-for="(g, i) in analysis.conflicts" :key="i" class="card">
        <h3>„{{ g.questions[0].text }}“</h3>
        <div class="compare">
          <div v-for="q in g.questions" :key="q.id">
            <div class="muted" style="margin-bottom: 0.3rem">📄 {{ where(q) }}</div>
            <ul class="answers-list">
              <li v-for="(a, j) in q.answers" :key="j" :class="{ correct: a.is_correct }">{{ answerText(a.text, q.question_type) }}</li>
            </ul>
          </div>
        </div>
      </div>
    </template>

    <!-- similar -->
    <template v-if="tab === 'similar'">
      <p class="muted">
        Unterschiedlich formuliert, inhaltlich aber fast gleich. Liegen beide in derselben Kategorie, kann eine
        Person in einem Test zweimal fast dieselbe Frage bekommen. Entfernen Sie eine davon in Moodle oder verschieben Sie sie in eine andere Kategorie.
      </p>
      <p v-if="trimmed.similar" class="notice info">{{ trimmed.similar }} Mit der Fragenbank-Suche und ihren Filtern finden Sie jede einzelne.</p>
      <p v-if="!analysis.similar.length" class="notice success">Keine ähnlichen Fragen gefunden. ✓</p>
      <div v-for="p in analysis.similar" :key="p.a.id + '-' + p.b.id" class="card">
        <div class="card-head" style="margin-bottom: 0.5rem">
          <span class="badge violet">{{ Math.round(p.score * 100) }} % gleiche Wörter</span>
          <span v-if="p.a.category === p.b.category" class="badge warn">gleiche Kategorie</span>
        </div>
        <div class="compare">
          <div v-for="q in [p.a, p.b]" :key="q.id">
            <strong>{{ q.name }}</strong>
            <p style="margin: 0.3rem 0">{{ q.text }}</p>
            <div class="muted">📚 {{ q.fach }} / {{ q.category }} · 📄 {{ where(q) }}</div>
          </div>
        </div>
      </div>
    </template>

    <!-- broken -->
    <template v-if="tab === 'issues'">
      <p class="muted">Fragen, die in Moodle nicht richtig funktionieren würden.</p>
      <p v-if="trimmed.issues" class="notice info">{{ trimmed.issues }} Mit der Fragenbank-Suche und ihren Filtern finden Sie jede einzelne.</p>
      <p v-if="!analysis.issues.length" class="notice success">Keine fehlerhaften Fragen gefunden. ✓</p>
      <div v-else class="card"><table class="list">
        <thead><tr><th>Frage</th><th>Problem</th><th>Herkunft</th></tr></thead>
        <tbody>
          <tr v-for="i in analysis.issues" :key="i.question.id">
            <td>
              <router-link :to="bankLink(i.question)"><strong>{{ i.question.name }}</strong></router-link>
              <div class="muted">{{ typeLabel(i.question.question_type) }} · {{ i.question.text }}</div>
            </td>
            <td><div v-for="pr in i.problems" :key="pr" class="badge warn" style="white-space: normal">{{ pr }}</div></td>
            <td class="muted">{{ where(i.question) }}</td>
          </tr>
        </tbody>
      </table></div>
    </template>

    <!-- exact duplicates -->
    <template v-if="tab === 'exact'">
      <p class="muted">
        Diese Fragen kommen in mehreren Dateien identisch vor (auch wenn die Antworten anders sortiert sind).
        Das ist <strong>kein Fehler</strong>: Die Fragenbank speichert sie nur einmal, und beim Export entsteht kein Duplikat.
      </p>
      <p v-if="trimmed.exact" class="notice info">{{ trimmed.exact }} Mit der Fragenbank-Suche und ihren Filtern finden Sie jede einzelne.</p>
      <p v-if="!analysis.exact.length" class="notice success">Keine Frage kommt mehrfach vor.</p>
      <div v-else class="card"><table class="list">
        <thead><tr><th>Frage</th><th>Dateien</th></tr></thead>
        <tbody>
          <tr v-for="e in analysis.exact" :key="e.question.id">
            <td>
              <router-link :to="bankLink(e.question)"><strong>{{ e.question.name }}</strong></router-link>
              <div class="muted">{{ e.question.text }}</div>
            </td>
            <td>
              <div class="chips">
                <span v-for="o in e.question.origins" :key="o.file_id" class="chip">📄 {{ o.filename }}</span>
              </div>
            </td>
          </tr>
        </tbody>
      </table></div>
    </template>
  </template>
</template>
