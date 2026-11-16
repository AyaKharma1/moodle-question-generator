// Whether the fictitious demo data is loaded. Shared so the banner (App) and
// the dashboard stay in sync.
import { reactive } from "vue";
import { api } from "./api";

export const demoState = reactive({ loaded: false, notice: "" });

export async function refreshDemo(): Promise<void> {
  try {
    const s = await api.demoStatus();
    demoState.loaded = s.loaded;
    demoState.notice = s.notice;
  } catch {
    demoState.loaded = false;
  }
}
