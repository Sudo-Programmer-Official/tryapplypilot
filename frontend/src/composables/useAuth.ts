import { computed, ref } from "vue";

import { fetchCurrentUser, login, logout, signup } from "../api/auth.api";
import {
  AUTH_SESSION_CLEARED_EVENT,
  clearAuthSession,
  getStoredUserSnapshot,
  hasStoredSession,
  RequestError,
  storeUserSnapshot,
} from "../api/client";
import type { AuthUser, UserRole } from "../types";

const user = ref<AuthUser | null>(null);
const loading = ref(false);
const initialized = ref(false);
let authSessionListenerRegistered = false;

export function homeRouteForRole(role: UserRole): string {
  return role === "admin" || role === "super_admin" ? "/admin/dashboard" : "/user/dashboard";
}

export function useAuth() {
  if (!authSessionListenerRegistered && typeof window !== "undefined") {
    window.addEventListener(AUTH_SESSION_CLEARED_EVENT, () => {
      user.value = null;
      initialized.value = true;
      loading.value = false;
    });
    authSessionListenerRegistered = true;
  }

  async function init(): Promise<void> {
    if (initialized.value || loading.value) {
      return;
    }
    loading.value = true;
    try {
      if (hasStoredSession()) {
        const cachedUser = getStoredUserSnapshot();
        if (cachedUser) {
          user.value = cachedUser;
        }
        const payload = await fetchCurrentUser();
        user.value = payload.user;
        storeUserSnapshot(payload.user);
      }
    } catch (err) {
      if (err instanceof RequestError && (err.status === 401 || err.status === 403)) {
        clearAuthSession();
        user.value = null;
      }
    } finally {
      loading.value = false;
      initialized.value = true;
    }
  }

  async function refresh(): Promise<AuthUser | null> {
    await init();
    if (!hasStoredSession()) {
      user.value = null;
      return null;
    }
    const payload = await fetchCurrentUser();
    user.value = payload.user;
    storeUserSnapshot(payload.user);
    return payload.user;
  }

  async function loginWithPassword(email: string, password: string): Promise<AuthUser> {
    const nextUser = await login(email, password);
    user.value = nextUser;
    storeUserSnapshot(nextUser);
    initialized.value = true;
    return nextUser;
  }

  async function signupWithPassword(email: string, password: string, fullName: string): Promise<AuthUser> {
    const nextUser = await signup(email, password, fullName);
    user.value = nextUser;
    storeUserSnapshot(nextUser);
    initialized.value = true;
    return nextUser;
  }

  async function logoutCurrentUser(): Promise<void> {
    await logout();
    user.value = null;
    initialized.value = true;
  }

  function setUser(nextUser: AuthUser): void {
    user.value = nextUser;
    storeUserSnapshot(nextUser);
  }

  return {
    user,
    loading,
    initialized,
    isAuthenticated: computed(() => Boolean(user.value)),
    isAdmin: computed(() => user.value?.role === "admin" || user.value?.role === "super_admin"),
    homeRoute: computed(() => (user.value ? homeRouteForRole(user.value.role) : "/")),
    init,
    refresh,
    setUser,
    loginWithPassword,
    signupWithPassword,
    logoutCurrentUser,
  };
}
