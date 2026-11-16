<script setup lang="ts">
import Icon from "../components/Icon.vue";
import { computed, onMounted, ref } from "vue";
import { api, type ExportRecord, type ImportFile } from "../api";
import { formatDate } from "../bank";

const imports = ref<ImportFile[]>([]);
const exports = ref<ExportRecord[]>([]);
const open = ref<number | null>(null);
const loading = ref(true);
const filter = ref("");

function words(): string[] {
  return filter.value.toLowerCase().split(/\s+/).filter(Boolean);
}
const visibleImports = computed(() => imports.value.filter((f) => {
  const hay = `${f.filename} ${f.fach ?? ""} ${f.categories.join(" ")}`.toLowerCase();
  return words().every((w) => hay.includes(w));
}));
// an export matches by its file name or by the name of any question in it
const visibleExports = computed(() => exports.value.filter((e) => {
  const hay = `${e.filename} ${e.question_names.join(" ")}`.toLowerCase();
  return words().every((w) => hay.includes(w));
}));

onMounted(async () => {
  try {
    [imports.value, exports.value] = await Promise.all([api.listImportFiles(), api.exportHistory()]);
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="page-head">
    <h1>Verlauf</h1>
    <p>Welche Dateien importiert und welche XML-Dateien für Moodle erstellt wurden, und welche Fragen darin stehen.</p>
  </div>

  <div v-if="loading" class="muted">Lädt…</div>
  <template v-else>
    <div class="card">
      <input v-model="filter" class="searchbox" type="search" aria-label="Verlauf durchsuchen"
             placeholder="Dateien durchsuchen: Dateiname, Kategorie oder Name einer Frage …" />
    </div>

    <div class="card">
      <h2><Icon name="upload" /> Exportierte Dateien</h2>
      <p v-if="!exports.length" class="muted">
        Noch nichts exportiert. Fragen wählen Sie in der <router-link to="/bank">Fragenbank</router-link> aus.
      </p>
      <p v-else-if="!visibleExports.length" class="muted">Keine exportierte Datei passt zur Suche.</p>
      <table v-else class="list">
        <thead><tr><th>Datei</th><th>Fragen</th><th>Erstellt am</th><th /></tr></thead>
        <tbody>
          <template v-for="e in visibleExports" :key="e.id">
            <tr>
              <td><strong>{{ e.filename }}</strong><div v-if="e.note" class="muted">{{ e.note }}</div></td>
              <td>{{ e.question_count }}</td>
              <td class="muted">{{ formatDate(e.created_at) }}</td>
              <td style="text-align: right">
                <button class="ghost small" @click="open = open === e.id ? null : e.id">
                  {{ open === e.id ? "Fragen ausblenden" : "Fragen anzeigen" }}
                </button>
              </td>
            </tr>
            <tr v-if="open === e.id">
              <td colspan="4">
                <p v-if="e.summary" class="muted" style="margin-top: 0">
                  Zum Exportzeitpunkt offen: {{ e.summary.warnings.counts.critical }} kritisch, {{ e.summary.warnings.counts.review }} überprüfen, {{ e.summary.warnings.counts.info }} Information.
                  Kategorien: {{ e.summary.categories.map((c) => `${c.path} (${c.count})`).join(", ") }}.
                </p>
                <div class="chips">
                  <span v-for="(name, i) in e.question_names" :key="i" class="chip">{{ name }}</span>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <div class="card">
      <h2><Icon name="inbox" /> Importierte Dateien</h2>
      <p v-if="!imports.length" class="muted">Noch nichts importiert. <router-link to="/import">Jetzt importieren →</router-link></p>
      <p v-else-if="!visibleImports.length" class="muted">Keine importierte Datei passt zur Suche.</p>
      <table v-else class="list">
        <thead><tr><th>Datei</th><th>Fach</th><th>Fragen</th><th>Importiert am</th></tr></thead>
        <tbody>
          <tr v-for="f in visibleImports" :key="f.id">
            <td><router-link :to="{ name: 'bank', query: { file: f.id } }">{{ f.filename }}</router-link></td>
            <td>{{ f.fach || "aus Kategorie" }}</td>
            <td>{{ f.question_count }} <span class="muted">({{ f.new_count }} neu)</span></td>
            <td class="muted">{{ formatDate(f.created_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </template>
</template>
