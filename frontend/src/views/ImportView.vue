<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api, ApiError, type ImportFile, type ImportSummary } from "../api";
import { formatDate, plural } from "../bank";

const picked = ref<File[]>([]);
const fach = ref("");
const results = ref<ImportSummary[]>([]);
const files = ref<ImportFile[]>([]);
const error = ref("");
const busy = ref(false);
const over = ref(false);
const input = ref<HTMLInputElement | null>(null);

async function refresh() {
  files.value = await api.listImportFiles();
}
onMounted(refresh);

function addFiles(list: FileList | null | undefined) {
  if (!list) return;
  const known = new Set(picked.value.map((f) => f.name + f.size));
  picked.value = [...picked.value, ...[...list].filter((f) => !known.has(f.name + f.size))];
}

function onDrop(e: DragEvent) {
  over.value = false;
  addFiles(e.dataTransfer?.files);
}

function removePicked(i: number) {
  picked.value = picked.value.filter((_, idx) => idx !== i);
}

async function runImport() {
  error.value = "";
  if (picked.value.length === 0) {
    error.value = "Bitte mindestens eine Moodle-XML-Datei auswählen.";
    return;
  }
  busy.value = true;
  try {
    results.value = await api.importFiles(picked.value, fach.value.trim() || undefined);
    picked.value = [];
    if (input.value) input.value.value = "";
    await refresh();
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "Import fehlgeschlagen.";
  } finally {
    busy.value = false;
  }
}

async function removeFile(f: ImportFile) {
  if (!confirm(`„${f.filename}“ aus der Fragenbank entfernen? Fragen, die nur in dieser Datei vorkommen, werden gelöscht.`)) return;
  await api.deleteImportFile(f.id);
  results.value = results.value.filter((r) => r.file_id !== f.id);
  await refresh();
}

function kb(n: number) {
  return `${(n / 1024).toFixed(1)} KB`;
}
</script>

<template>
  <div class="page-head">
    <h1>Moodle-XML importieren</h1>
    <p>
      In Moodle: <strong>Fragensammlung → Exportieren → „Moodle-XML-Format“</strong>. Die exportierten Dateien
      können Sie hier hochladen, auch mehrere gleichzeitig. Doppelte Fragen werden automatisch erkannt.
    </p>
  </div>

  <div class="card">
    <div v-if="error" class="notice error">{{ error }}</div>

    <div class="dropzone" :class="{ over }" @click="input?.click()"
         @dragover.prevent="over = true" @dragleave="over = false" @drop.prevent="onDrop">
      <div class="icon">📄</div>
      <strong>XML-Dateien hierher ziehen oder klicken</strong>
      <div class="muted">Moodle-XML, max. 10 MB pro Datei, bis zu 20 Dateien</div>
      <input ref="input" type="file" accept=".xml" multiple style="display: none"
             @change="addFiles(($event.target as HTMLInputElement).files)" />
    </div>

    <ul v-if="picked.length" style="margin: 0.75rem 0 0; padding-left: 1.1rem">
      <li v-for="(f, i) in picked" :key="f.name + f.size">
        {{ f.name }} <span class="muted">({{ kb(f.size) }})</span>
        <button class="ghost small" @click="removePicked(i)">entfernen</button>
      </li>
    </ul>

    <label for="fach">Fach (optional)</label>
    <input id="fach" v-model="fach" placeholder="z. B. Computersysteme" />
    <div class="hint">
      Leer lassen: Das Fach wird aus der obersten Moodle-Kategorie übernommen.
      Ausgefüllt: Alle Fragen dieser Dateien kommen in dieses Fach, die Moodle-Kategorien bleiben darunter erhalten.
    </div>

    <div class="row" style="margin-top: 1rem">
      <button :disabled="busy || picked.length === 0" @click="runImport">
        <span v-if="busy" class="spinner" /> {{ picked.length || "" }} Datei(en) importieren
      </button>
    </div>
  </div>

  <div v-if="results.length" class="card">
    <h2>Ergebnis</h2>
    <div v-for="r in results" :key="r.filename" class="card tight">
      <div class="card-head" style="margin-bottom: 0.4rem">
        <strong>📄 {{ r.filename }}</strong>
        <span v-if="r.error" class="badge danger">Fehler</span>
        <span v-else class="badge ok">Importiert</span>
      </div>
      <div v-if="r.error" class="notice error" style="margin: 0">{{ r.error }}</div>
      <template v-else>
        <div class="chips">
          <span class="chip"><strong>{{ r.total }}</strong> Fragen gelesen</span>
          <span class="chip"><strong>{{ r.new }}</strong> neu</span>
          <span v-if="r.existing" class="chip"><strong>{{ r.existing }}</strong> schon vorhanden (nicht doppelt gespeichert)</span>
          <span v-if="r.conflicts" class="badge danger">{{ plural(r.conflicts, "Widerspruch", "Widersprüche") }}</span>
        </div>
        <p class="muted" style="margin: 0.5rem 0 0">Kategorien: {{ r.categories.join(", ") || "–" }}</p>
        <div class="row" style="margin-top: 0.5rem">
          <router-link :to="{ name: 'bank', query: { file: r.file_id } }" class="button secondary small">Fragen ansehen</router-link>
          <router-link v-if="r.conflicts" to="/pruefung" class="button secondary small">Widersprüche prüfen</router-link>
        </div>
      </template>
    </div>
  </div>

  <div class="card">
    <h2>Importierte Dateien</h2>
    <p v-if="files.length === 0" class="muted">Noch keine Dateien importiert.</p>
    <table v-else class="list">
      <thead><tr><th>Datei</th><th>Fach</th><th>Fragen</th><th>Importiert am</th><th /></tr></thead>
      <tbody>
        <tr v-for="f in files" :key="f.id">
          <td><router-link :to="{ name: 'bank', query: { file: f.id } }">{{ f.filename }}</router-link></td>
          <td>{{ f.fach || "aus Kategorie" }}</td>
          <td>{{ f.question_count }} <span class="muted">({{ f.new_count }} neu)</span></td>
          <td class="muted">{{ formatDate(f.created_at) }}</td>
          <td style="text-align: right"><button class="ghost small" @click="removeFile(f)">Entfernen</button></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
