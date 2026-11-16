// Thin, typed API client. The auth token is kept in localStorage and attached
// to every request. All calls go through request() so error handling and the
// Authorization header live in one place.

export type QuestionType = "multiple_choice" | "true_false" | "short_answer";
export type Difficulty = "easy" | "medium" | "hard";
export type Language = "de" | "en";

export interface AnswerOut {
  id: number;
  text: string;
  is_correct: boolean;
  feedback: string | null;
  position: number;
}

export interface Origin {
  file_id: number;
  filename: string;
  fach: string | null;
  category: string | null;
}

export interface Question {
  id: number;
  document_id: number | null;
  // Imported questions can carry any Moodle type (essay, matching, ...).
  question_type: QuestionType | string;
  question_text: string;
  explanation: string;
  difficulty: Difficulty;
  language: Language;
  status: "pending" | "approved" | "rejected";
  grounding_score: number;
  is_duplicate: boolean;
  ai_generated: boolean;
  answers: AnswerOut[];
  created_at: string;
  updated_at: string;
  name: string | null;
  fach: string | null;
  category: string | null;
  moodle_type: string | null;
  origins: Origin[];
  exported_in: string[];
  flags: { label: string; kind: string; detail?: string }[];
  decision: Decision | null;
  decision_note: string | null;
}

export type Decision = "reviewed" | "excluded";
export type Severity = "critical" | "review" | "info";

export interface ImportReport {
  types: { type: string; name: string; count: number }[];
  categories: { name: string; count: number }[];
  media: { with_files: number; missing: number };
  warnings: { code: string; severity: Severity; text: string; count: number }[];
}

export interface SelectionCheck {
  similar_pairs: number;
  similar_examples: string[];
  conflict_groups: number;
  conflict_examples: string[];
  broken: number;
  broken_examples: string[];
}

export interface QuestionFilter {
  status?: string;
  fach?: string;
  category?: string;
  import_file_id?: number;
  source?: "import" | "ai";
  q?: string;
}

export interface ImportSummary {
  file_id: number | null;
  filename: string;
  fach: string | null;
  total: number;
  new: number;
  existing: number;
  conflicts: number;
  categories: string[];
  error: string | null;
  report: ImportReport | null;
}

export interface ImportFile {
  id: number;
  filename: string;
  fach: string | null;
  size_bytes: number;
  question_count: number;
  new_count: number;
  created_at: string;
  categories: string[];
  report: ImportReport | null;
}

export interface FacetValue {
  value: string;
  count: number;
}

export interface Facets {
  fach: FacetValue[];
  category: FacetValue[];
  type: FacetValue[];
  file: (FacetValue & { id: number })[];
}

export interface BankPage {
  items: Question[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  facets: Facets;
}

export interface BankQuery {
  q?: string;
  fach?: string;
  category?: string;
  file?: number | string;
  type?: string;
  source?: string;
  flag?: string;
  exported?: string;
  decision?: string;
  sort?: string;
  page?: number;
  page_size?: number;
}

export interface PlanSlot {
  fach: string | null;
  category: string;
  count?: number;
  percent?: number;
}

export interface PlanRequest {
  slots: PlanSlot[];
  students: number;
  seed?: number;
  only_unused?: boolean;
  total?: number;
}

export interface PaperStats {
  pairs_compared: number;
  students_compared: number;
  overlap_histogram: { shared: number; pairs: number }[];
  avg_overlap: number;
  max_overlap: number;
  unique_papers: number;
  students_with_identical_paper: number;
  usage_min: number;
  usage_max: number;
}

export interface PlanSlotResult {
  fach: string | null;
  category: string;
  label: string;
  count: number;
  pool_before: number;
  pool_size: number;
  enough: boolean;
  level: "impossible" | "small" | "tight" | "good";
  shared_expected: number | null;
  recommended_min: number;
  missing_for_recommended: number;
  coverage_percent: number;
  removed: { id: number; name: string; reason: string }[];
  pool: { id: number; name: string }[];
}

export interface Fairness {
  expected_shared: number;
  log10_variants: number;
  expected_identical_pairs: number;
  p_no_overlap_pair: number;
  max_students_without_overlap: number;
  disjoint_possible: boolean;
  identical_unavoidable: boolean;
}

export interface PlanResult {
  seed: number;
  students: number;
  per_paper: number;
  ok: boolean;
  slots: PlanSlotResult[];
  pool_ids: number[];
  warnings: string[];
  variants_log10: number | null;
  random: PaperStats | null;
  balanced: PaperStats | null;
  fairness: Fairness | null;
  statements: { kind: "calculated" | "simulated" | "not_guaranteed"; text: string }[];
  sample_papers: { student: number; questions: { id: number; name: string; category: string }[] }[];
}

export interface BankOverview {
  totals: {
    questions: number;
    files: number;
    fachs: number;
    categories: number;
    duplicates: number;
    conflicts: number;
    similar: number;
    similar_capped: boolean;
    issues: number;
  };
  tree: { fach: string; count: number; categories: { name: string; count: number }[] }[];
  quality: {
    open: Record<Severity, number>;
    done: Record<Severity, number>;
    reviewed: number;
    excluded: number;
    open_conflicts: number;
  };
}

export interface BriefQuestion {
  id: number;
  name: string | null;
  text: string;
  question_type: string;
  fach: string | null;
  category: string | null;
  origins: Origin[];
  answers: { text: string; is_correct: boolean }[];
}

export interface BankAnalysis {
  counts: { exact: number; conflicts: number; similar: number; issues: number };
  limit: number;
  similar_capped: boolean;
  exact: { question: BriefQuestion; count: number }[];
  conflicts: { questions: BriefQuestion[] }[];
  similar: { a: BriefQuestion; b: BriefQuestion; score: number }[];
  issues: { question: BriefQuestion; problems: string[] }[];
}

export interface ExportRecord {
  id: number;
  filename: string;
  question_count: number;
  question_ids: number[];
  question_names: string[];
  created_at: string | null;
  note: string | null;
  summary: ExportSummary | null;
}

export interface ExportSummary {
  count: number;
  types: { type: string; count: number }[];
  categories: { path: string; count: number }[];
  warnings: { counts: Record<Severity, number>; examples: { question_id: number; code: string; title: string; detail: string }[] };
  previously_exported: number;
}

export interface ExportPreview extends ExportSummary {
  excluded: { id: number; name: string | null; reason: string }[];
  can_export: boolean;
  blocked_reason: string | null;
  unchanged_originals: number;
  generated: number;
  previous_files: string[];
  filename: string;
  disclaimer: string;
  checklist: string[];
}

export interface CatalogEntry { severity: Severity; severity_label: string; title: string; why: string; action: string }

export interface FindingItem {
  question_id: number;
  code: string;
  severity: Severity;
  detail: string;
  related: number[];
  done: boolean;
  decision: Decision | null;
  question: {
    id: number; name: string | null; type_name: string; fach: string | null; category: string | null;
    text: string; files: string[]; decision: Decision | null; decision_note: string | null;
  };
}

export interface FindingsPage {
  summary: {
    open: Record<Severity, number>;
    done: Record<Severity, number>;
    by_code: Record<string, { open: number; done: number }>;
  };
  catalog: Record<string, CatalogEntry>;
  items: FindingItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface VariantOrigin { file_id: number | null; filename: string; fach: string | null; category: string | null; imported_at: string | null }

export interface Variant {
  id: number;
  name: string | null;
  label: string;
  fach: string | null;
  category: string | null;
  decision: Decision | null;
  decision_note: string | null;
  origins: VariantOrigin[];
  answers: { text: string; is_correct: boolean; differs: boolean }[];
}

export interface ConflictGroup { key: string; text: string; resolved: boolean; variants: Variant[] }

export interface QuestionHistory {
  question: {
    id: number; name: string | null; question_type: string; type_name: string; fach: string | null; category: string | null;
    status: string; ai_generated: boolean; text: string; explanation: string;
    answers: { text: string; is_correct: boolean; feedback: string }[];
    decision: Decision | null; decision_note: string | null; decided_at: string | null; created_at: string | null;
  };
  origins: VariantOrigin[];
  conflict: boolean;
  variants: Variant[];
  similar: { id: number; name: string | null; text: string; score: number; fach: string | null; category: string | null }[];
  exports: { id: number; filename: string; created_at: string | null; note: string | null }[];
  findings: (FindingItem & { title: string; why: string; action: string })[];
}

export interface DemoStatus { loaded: boolean; files: string[]; fach: string; notice: string }

export interface DocumentOut {
  id: number;
  original_filename: string;
  extension: string;
  size_bytes: number;
  created_at: string;
}

export interface GenerateResponse {
  provider: string;
  created: Question[];
  parse_errors: string[];
  warnings: Record<number, string[]>;
}

const TOKEN_KEY = "mqg_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

// Called when the server says the login is no longer valid (token expired).
let unauthorizedHandler: (() => void) | null = null;
export function onUnauthorized(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

const FIELD_NAMES: Record<string, string> = {
  password: "Das Passwort",
  email: "Die E-Mail-Adresse",
  full_name: "Der Name",
  students: "Die Anzahl der Studierenden",
  count: "„Fragen pro Person“",
  slots: "Die Kategorien",
  question_text: "Der Fragetext",
  explanation: "Die Erklärung",
  answers: "Die Antworten",
  filename: "Der Dateiname",
  question_ids: "Die Auswahl",
  total: "Die Gesamtzahl der Fragen",
  percent: "Der Prozentanteil",
  note: "Die Notiz",
  category_prefix: "Der Ordnername",
};

// FastAPI/pydantic reports invalid input as a list of objects. Turn them into
// sentences a lecturer can act on instead of "[object Object]".
export function describeDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const parts = detail.map((item) => {
      if (typeof item === "string") return item;
      if (item && typeof item === "object") {
        const e = item as { type?: string; loc?: unknown[]; msg?: string; ctx?: Record<string, unknown> };
        const field = [...(e.loc ?? [])].reverse().find((p) => typeof p === "string") as string | undefined;
        const who = (field && FIELD_NAMES[field]) || (field ? `Das Feld „${field}“` : "Eine Eingabe");
        switch (e.type) {
          case "missing": return `${who} fehlt.`;
          case "string_too_short": return `${who} ist zu kurz (mindestens ${e.ctx?.min_length ?? "?"} Zeichen).`;
          case "string_too_long": return `${who} ist zu lang (höchstens ${e.ctx?.max_length ?? "?"} Zeichen).`;
          case "too_short": return `${who} braucht mindestens ${e.ctx?.min_length ?? "einen"} Eintrag.`;
          case "too_long": return `${who} darf höchstens ${e.ctx?.max_length ?? "?"} Einträge haben.`;
          case "greater_than_equal": return `${who} ist zu klein (mindestens ${e.ctx?.ge ?? "?"}).`;
          case "less_than_equal": return `${who} ist zu groß (höchstens ${e.ctx?.le ?? "?"}).`;
          case "int_parsing":
          case "int_from_float": return `${who} muss eine ganze Zahl sein.`;
          case "value_error": return `${who} ist nicht zulässig.`;
          default: return `${who} ist ungültig.`;
        }
      }
      return fallback;
    });
    return [...new Set(parts)].join(" ") || fallback;
  }
  return fallback;
}

function jsonPost(body: unknown): RequestInit {
  return { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let res: Response;
  try {
    res = await fetch(path, { ...init, headers });
  } catch {
    throw new ApiError(0, "Keine Verbindung zum Server. Bitte prüfen, ob die Anwendung noch läuft, und die Seite neu laden.");
  }

  if (res.status === 204) return undefined as T;
  const isJson = res.headers.get("content-type")?.includes("application/json");
  const body = isJson ? await res.json() : await res.text();

  if (!res.ok) {
    const fallback = `Anfrage fehlgeschlagen (Fehler ${res.status}).`;
    const message = describeDetail(isJson ? (body as any).detail : undefined, fallback);
    // An expired login must send the user back to the sign-in page. A wrong
    // password at the sign-in page itself is a normal error, not an expiry.
    if (res.status === 401 && token && !path.startsWith("/api/auth/login")) {
      setToken(null);
      unauthorizedHandler?.();
    }
    throw new ApiError(res.status, message);
  }
  return body as T;
}

function toQuery(params: object): string {
  const sp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") sp.set(key, String(value));
  }
  const qs = sp.toString();
  return qs ? `?${qs}` : "";
}

export const api = {
  // auth
  async register(email: string, password: string, full_name?: string) {
    return request("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, full_name }),
    });
  },
  async login(email: string, password: string): Promise<void> {
    const form = new URLSearchParams({ username: email, password });
    const data = await request<{ access_token: string }>("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form,
    });
    setToken(data.access_token);
  },
  async me() {
    return request<{ id: number; email: string; full_name: string | null; role: string }>(
      "/api/auth/me",
    );
  },

  // documents
  listDocuments: () => request<DocumentOut[]>("/api/documents"),
  async uploadDocument(file: File): Promise<DocumentOut> {
    const fd = new FormData();
    fd.append("file", file);
    return request<DocumentOut>("/api/documents", { method: "POST", body: fd });
  },

  // generation
  generate: (payload: {
    document_id: number;
    question_type: QuestionType;
    num_questions: number;
    difficulty: Difficulty;
    language: Language;
    fach?: string;
    category?: string;
  }) =>
    request<GenerateResponse>("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),

  // question bank
  async importFiles(files: File[], fach?: string): Promise<ImportSummary[]> {
    const fd = new FormData();
    for (const f of files) fd.append("files", f);
    if (fach) fd.append("fach", fach);
    return request<ImportSummary[]>("/api/bank/import", { method: "POST", body: fd });
  },
  listImportFiles: () => request<ImportFile[]>("/api/bank/files"),
  deleteImportFile: (id: number) =>
    request<void>(`/api/bank/files/${id}`, { method: "DELETE" }),
  overview: () => request<BankOverview>("/api/bank/overview"),
  analysis: () => request<BankAnalysis>("/api/bank/analysis"),
  // quality, history and decisions
  findings: (q: { severity?: string; code?: string; state?: string; page?: number; page_size?: number }) =>
    request<FindingsPage>(`/api/bank/findings${toQuery(q)}`),
  conflicts: (state: "open" | "done" = "open", page = 1) =>
    request<{ items: ConflictGroup[]; total: number; page: number; page_size: number }>(
      `/api/bank/conflicts${toQuery({ state, page })}`),
  decideConflict: (key: string, keep: number | null, note?: string) =>
    request<{ ids: number[] }>(`/api/bank/conflicts/${key}/decide`, jsonPost({ keep, note })),
  reopenConflict: (key: string) => request<{ ids: number[] }>(`/api/bank/conflicts/${key}/reopen`, { method: "POST" }),
  questionHistory: (id: number) => request<QuestionHistory>(`/api/bank/questions/${id}/history`),
  decideQuestion: (id: number, state: "open" | Decision, note?: string) =>
    request<{ id: number; decision: Decision | null }>(`/api/bank/questions/${id}/decision`, jsonPost({ state, note })),

  // demo mode
  demoStatus: () => request<DemoStatus>("/api/demo"),
  loadDemo: () => request<{ loaded: boolean }>("/api/demo/load", { method: "POST" }),
  removeDemo: () => request<{ questions_removed: number }>("/api/demo", { method: "DELETE" }),

  exportPreview: (question_ids: number[], filename?: string, category_prefix?: string) =>
    request<ExportPreview>("/api/export/preview", jsonPost({ question_ids, filename, category_prefix: category_prefix || undefined })),
  exportHistory: () => request<ExportRecord[]>("/api/export/history"),

  // search (server side, paged)
  bankQuestions: (query: BankQuery) => request<BankPage>(`/api/bank/questions${toQuery(query)}`),
  bankSelectableIds: (query: BankQuery, excludeFlagged = false) =>
    request<{ ids: number[]; total: number; truncated: boolean }>(
      `/api/bank/selectable-ids${toQuery({ ...query, page: undefined, page_size: undefined, exclude_flagged: excludeFlagged || undefined })}`,
    ),

  checkSelection: (ids: number[]) =>
    request<SelectionCheck>("/api/bank/check-selection", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    }),

  // test planner
  plan: (body: PlanRequest) =>
    request<PlanResult>("/api/planner/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  async planCsv(body: PlanRequest): Promise<Blob> {
    const token = getToken();
    const res = await fetch("/api/planner/plan.csv", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(res.status, describeDetail((err as any).detail, `Fehler ${res.status}.`));
    }
    return res.blob();
  },

  // questions
  listQuestions: (filter: QuestionFilter | string = {}) => {
    const f = typeof filter === "string" ? { status: filter } : filter;
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(f)) {
      if (value !== undefined && value !== "") params.set(key, String(value));
    }
    const qs = params.toString();
    return request<Question[]>(`/api/questions${qs ? `?${qs}` : ""}`);
  },
  updateQuestion: (id: number, payload: Record<string, unknown>) =>
    request<Question>(`/api/questions/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  deleteQuestion: (id: number) => request<void>(`/api/questions/${id}`, { method: "DELETE" }),
  review: (id: number, action: "approve" | "reject", comment?: string) =>
    request<Question>(`/api/questions/${id}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, comment }),
    }),
  regenerate: (id: number) =>
    request<Question>(`/api/questions/${id}/regenerate`, { method: "POST" }),

  // export (returns the raw XML as a Blob to download)
  async exportXml(question_ids: number[], filename?: string, category_prefix?: string, note?: string): Promise<Blob> {
    const token = getToken();
    const res = await fetch("/api/export", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ question_ids, filename, category_prefix: category_prefix || undefined, note: note || undefined }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new ApiError(res.status, describeDetail((body as any).detail, `Export fehlgeschlagen (Fehler ${res.status}).`));
    }
    return res.blob();
  },
};
