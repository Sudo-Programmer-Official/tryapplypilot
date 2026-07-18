import { computed, ref } from "vue";

import { fetchDashboard } from "../api/admin.api";
import type { DashboardSnapshot } from "../types";

export function useDashboard() {
  const snapshot = ref<DashboardSnapshot | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);

  async function load(): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      snapshot.value = await fetchDashboard();
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to load dashboard.";
    } finally {
      loading.value = false;
    }
  }

  return {
    snapshot,
    loading,
    error,
    jobs: computed(() => snapshot.value?.jobs ?? []),
    alerts: computed(() => snapshot.value?.alerts ?? []),
    sources: computed(() => snapshot.value?.sources ?? []),
    settings: computed(() => snapshot.value?.settings ?? null),
    load,
  };
}
