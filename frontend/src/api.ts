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
  flags: { label: string; kind: string }[];
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
  sort?: string;
  page?: number;
  page_size?: number;
}

export interface PlanSlot {
  fach: string | null;
  category: string;
  count: number;
}

export interface PlanRequest {
  slots: PlanSlot[];
  students: number;
  seed?: number;
  only_unused?: boolean;
}

export interface PaperStats {
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
  removed: { id: number; name: string; reason: string }[];
  pool: { id: number; name: string }[];
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
}

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

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(path, { ...init, headers });

  if (res.status === 204) return undefined as T;
  const isJson = res.headers.get("content-type")?.includes("application/json");
  const body = isJson ? await res.json() : await res.text();

  if (!res.ok) {
    const detail = isJson ? (body as any).detail : body;
    const msg = Array.isArray(detail) ? detail.join("; ") : String(detail ?? res.statusText);
    throw new ApiError(res.status, msg);
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
      throw new ApiError(res.status, (err as any).detail ?? res.statusText);
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
  async exportXml(question_ids: number[], filename?: string, category_prefix?: string): Promise<Blob> {
    const token = getToken();
    const res = await fetch("/api/export", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ question_ids, filename, category_prefix: category_prefix || undefined }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new ApiError(res.status, (body as any).detail ?? res.statusText);
    }
    return res.blob();
  },
};
