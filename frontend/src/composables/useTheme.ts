import { computed, ref } from "vue";

import type { ResolvedTheme, ThemeMode } from "../types";

const STORAGE_KEY = "tryapplypilot-theme";
const mode = ref<ThemeMode>("system");
const resolvedTheme = ref<ResolvedTheme>("light");
let initialized = false;
let media: MediaQueryList | null = null;

function applyTheme(): void {
  const actualTheme: ResolvedTheme =
    mode.value === "system" ? (media?.matches ? "dark" : "light") : mode.value;
  resolvedTheme.value = actualTheme;
  document.documentElement.dataset.theme = actualTheme;
  document.documentElement.dataset.themeMode = mode.value;
}

export function useTheme() {
  function init(): void {
    if (initialized) {
      return;
    }
    initialized = true;
    media = window.matchMedia("(prefers-color-scheme: dark)");
    const storedMode = window.localStorage.getItem(STORAGE_KEY) as ThemeMode | null;
    if (storedMode === "light" || storedMode === "dark" || storedMode === "system") {
      mode.value = storedMode;
    }
    media.addEventListener("change", applyTheme);
    applyTheme();
  }

  function setMode(next: ThemeMode): void {
    mode.value = next;
    window.localStorage.setItem(STORAGE_KEY, next);
    applyTheme();
  }

  return {
    mode,
    resolvedTheme: computed(() => resolvedTheme.value),
    init,
    setMode,
  };
}
