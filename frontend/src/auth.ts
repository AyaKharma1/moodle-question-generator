// Minimal reactive auth state (no Pinia needed for an app this size).
import { reactive } from "vue";
import { api, getToken, setToken } from "./api";

interface User {
  id: number;
  email: string;
  full_name: string | null;
  role: string;
}

export const authState = reactive<{ user: User | null; ready: boolean }>({
  user: null,
  ready: false,
});

export async function loadUser(): Promise<void> {
  if (!getToken()) {
    authState.user = null;
    authState.ready = true;
    return;
  }
  try {
    authState.user = await api.me();
  } catch {
    setToken(null);
    authState.user = null;
  } finally {
    authState.ready = true;
  }
}

export async function login(email: string, password: string): Promise<void> {
  await api.login(email, password);
  await loadUser();
}

export function logout(): void {
  setToken(null);
  authState.user = null;
}

export function isAuthenticated(): boolean {
  return !!getToken();
}
