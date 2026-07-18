import { computed, ref } from "vue";

import { fetchCurrentUser, login, logout, signup } from "../api/auth.api";
import { clearAuthSession, hasStoredSession } from "../api/client";
import type { AuthUser, UserRole } from "../types";

const user = ref<AuthUser | null>(null);
const loading = ref(false);
const initialized = ref(false);

export function homeRouteForRole(role: UserRole): string {
  return role === "admin" || role === "super_admin" ? "/admin/dashboard" : "/user/dashboard";
}

export function useAuth() {
  async function init(): Promise<void> {
    if (initialized.value || loading.value) {
      return;
    }
    loading.value = true;
    try {
      if (hasStoredSession()) {
        const payload = await fetchCurrentUser();
        user.value = payload.user;
      }
    } catch {
      clearAuthSession();
      user.value = null;
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
    return payload.user;
  }

  async function loginWithPassword(email: string, password: string): Promise<AuthUser> {
    const nextUser = await login(email, password);
    user.value = nextUser;
    initialized.value = true;
    return nextUser;
  }

  async function signupWithPassword(email: string, password: string, fullName: string): Promise<AuthUser> {
    const nextUser = await signup(email, password, fullName);
    user.value = nextUser;
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
