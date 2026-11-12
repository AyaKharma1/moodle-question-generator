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
