import { computed, ref } from "vue";

import { fetchDashboard, fetchSchedulerStatus, runSchedulerNow } from "../api/admin.api";
import type { DashboardSnapshot, SchedulerStatusSnapshot } from "../types";

export function useDashboard() {
  const snapshot = ref<DashboardSnapshot | null>(null);
  const scheduler = ref<SchedulerStatusSnapshot | null>(null);
  const loading = ref(false);
  const runningNow = ref(false);
  const error = ref<string | null>(null);

  async function load(): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      const [dashboardResult, schedulerResult] = await Promise.allSettled([fetchDashboard(), fetchSchedulerStatus()]);
      if (dashboardResult.status === "rejected") {
        throw dashboardResult.reason;
      }
      snapshot.value = dashboardResult.value;
      scheduler.value = schedulerResult.status === "fulfilled" ? schedulerResult.value : dashboardResult.value.scheduler;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to load dashboard.";
    } finally {
      loading.value = false;
    }
  }

  async function triggerRunNow(): Promise<void> {
    runningNow.value = true;
    error.value = null;
    try {
      scheduler.value = await runSchedulerNow();
      await load();
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to run the scheduler.";
      throw err;
    } finally {
      runningNow.value = false;
    }
  }

  return {
    snapshot,
    scheduler,
    loading,
    runningNow,
    error,
    jobs: computed(() => snapshot.value?.jobs ?? []),
    alerts: computed(() => snapshot.value?.alerts ?? []),
    sources: computed(() => snapshot.value?.sources ?? []),
    settings: computed(() => snapshot.value?.settings ?? null),
    effectiveScheduler: computed(() => scheduler.value ?? snapshot.value?.scheduler ?? null),
    load,
    triggerRunNow,
  };
}
