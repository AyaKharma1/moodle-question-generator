// Shared helpers for the question bank views.
import { reactive } from "vue";

const TYPE_LABELS: Record<string, string> = {
  multiple_choice: "Multiple Choice",
  true_false: "Wahr / Falsch",
  short_answer: "Kurzantwort",
  essay: "Freitext",
  matching: "Zuordnung",
  numerical: "Numerisch",
  cloze: "Lückentext (Cloze)",
  multianswer: "Lückentext (Cloze)",
  ddwtos: "Drag & Drop",
  gapselect: "Lückenauswahl",
  description: "Beschreibung",
};

export function typeLabel(type: string): string {
  return TYPE_LABELS[type] ?? type;
}

// Moodle question text is HTML. Render it as plain text (never v-html): the
// parser does not run scripts, and textContent drops all markup.
export function plainText(html: string): string {
  if (!html) return "";
  // textContent glues paragraphs together; put a space before block tags.
  const spaced = html.replace(/<(\/?)(p|div|li|ul|ol|tr|td|th|h[1-6]|pre|br|table)\b/gi, " <$1$2");
  const doc = new DOMParser().parseFromString(spaced, "text/html");
  return (doc.body.textContent ?? "").replace(/\s+/g, " ").trim();
}

// Moodle stores true/false answers as the literal words "true"/"false".
export function answerText(text: string, type: string): string {
  const plain = plainText(text);
  if (type === "true_false" || type === "truefalse") {
    if (plain.toLowerCase() === "true") return "Wahr";
    if (plain.toLowerCase() === "false") return "Falsch";
  }
  return plain;
}

export function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`;
}

// Long question texts (e.g. Moodle "description" items with a whole lecture
// section) are shortened in lists; the full text is one click away.
export function shortText(text: string, max = 280): string {
  return text.length <= max ? text : text.slice(0, max).trimEnd() + "…";
}

export type DrawLevel = "impossible" | "small" | "tight" | "good";

export const LEVEL_TEXT: Record<DrawLevel, string> = {
  impossible: "zu wenige Fragen",
  small: "zu klein",
  tight: "knapp",
  good: "gut",
};
export const LEVEL_BADGE: Record<DrawLevel, string> = {
  impossible: "danger",
  small: "danger",
  tight: "warn",
  good: "ok",
};

export interface DrawCheck {
  level: DrawLevel;
  // Expected number of identical questions two students get.
  sharedOnAverage: number;
}

// Moodle draws `perTest` random questions from a category of `available`
// questions. Two students then share perTest² / available questions on
// average. That number decides whether the category is big enough.
export function checkRandomDraw(available: number, perTest: number): DrawCheck {
  if (perTest <= 0) return { level: "good", sharedOnAverage: 0 };
  if (available < perTest) return { level: "impossible", sharedOnAverage: perTest };
  const shared = (perTest * perTest) / available;
  let level: DrawLevel = "good";
  if (available <= 2 * perTest) level = "small";
  else if (available < 4 * perTest) level = "tight";
  return { level, sharedOnAverage: Math.round(shared * 10) / 10 };
}

// Questions picked in the Fragenbank, kept while switching pages.
export const selection = reactive<{ ids: Set<number> }>({ ids: new Set() });

export function toggleSelected(id: number): void {
  const next = new Set(selection.ids);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  selection.ids = next;
}

export function setSelected(ids: number[], selected: boolean): void {
  const next = new Set(selection.ids);
  for (const id of ids) {
    if (selected) next.add(id);
    else next.delete(id);
  }
  selection.ids = next;
}

export function formatDate(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString("de-DE", {
    day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------- search helpers

export function searchTerms(query: string | undefined): string[] {
  return (query ?? "").split(/\s+/).map((t) => t.trim()).filter(Boolean).slice(0, 8);
}

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export interface Segment {
  text: string;
  hit: boolean;
}

// Split text into plain and matching parts, so templates can wrap the hits in
// <mark> without v-html (the text is never interpreted as HTML).
export function highlight(text: string, terms: string[]): Segment[] {
  if (!text) return [];
  if (terms.length === 0) return [{ text, hit: false }];
  const re = new RegExp(terms.map(escapeRegExp).join("|"), "gi");
  const out: Segment[] = [];
  let last = 0;
  for (const m of text.matchAll(re)) {
    if (m[0] === "") continue;
    const at = m.index ?? 0;
    if (at > last) out.push({ text: text.slice(last, at), hit: false });
    out.push({ text: m[0], hit: true });
    last = at + m[0].length;
  }
  if (last < text.length) out.push({ text: text.slice(last), hit: false });
  return out;
}

// The part of a long text around the first hit (or its start without a hit).
export function excerpt(text: string, terms: string[], max = 280): string {
  if (text.length <= max) return text;
  const lower = text.toLowerCase();
  const at = terms.map((t) => lower.indexOf(t.toLowerCase())).filter((i) => i >= 0).sort((a, b) => a - b)[0];
  if (at === undefined || at < max - 60) return text.slice(0, max).trimEnd() + "…";
  const start = Math.max(0, at - 80);
  return "…" + text.slice(start, start + max).trim() + "…";
}

// Where in a question the search words were found (for "Treffer in …" chips).
export function matchFields(
  q: { name: string | null; question_text: string; explanation: string; answers: { text: string }[];
       fach: string | null; category: string | null; origins: { filename: string }[] },
  terms: string[],
): string[] {
  if (terms.length === 0) return [];
  const has = (text: string) => terms.some((t) => text.toLowerCase().includes(t.toLowerCase()));
  const found: string[] = [];
  if (has(q.name ?? "")) found.push("Name");
  if (has(plainText(q.question_text))) found.push("Fragetext");
  if (q.answers.some((a) => has(plainText(a.text)))) found.push("Antwort");
  if (has(plainText(q.explanation))) found.push("Erklärung");
  if (has(`${q.fach ?? ""} ${q.category ?? ""}`)) found.push("Kategorie");
  if (q.origins.some((o) => has(o.filename))) found.push("Dateiname");
  return found;
}

export const FLAG_LABELS: Record<string, string> = {
  any: "Mit irgendeinem Hinweis",
  conflict: "Widerspruch",
  similar: "Ähnliche Frage",
  issue: "Fehlerhaft",
  duplicate: "In mehreren Dateien",
};

export const SORT_LABELS: Record<string, string> = {
  newest: "Neueste zuerst",
  name: "Name A–Z",
  category: "Fach und Kategorie",
  files: "In den meisten Dateien",
};

export function formatNumber(n: number): string {
  return n.toLocaleString("de-DE");
}

// 10^x as a readable number: 4.3 -> "ca. 20.000", 12.5 -> "mehr als 1 Billion"
export function formatVariants(log10: number): string {
  if (log10 < 6) return `ca. ${formatNumber(Math.round(10 ** log10))}`;
  if (log10 < 9) return "mehr als 1 Million";
  if (log10 < 12) return "mehr als 1 Milliarde";
  return "mehr als 1 Billion";
}
