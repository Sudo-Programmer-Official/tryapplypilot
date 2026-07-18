import { computed, ref, type Ref } from "vue";

import { deleteUserSavedJob, fetchUserSavedJobs, saveUserSavedJob } from "../api/user.api";
import type { JobOpportunity } from "../types";

const savedJobIds = ref<string[]>([]);
const loadingSavedJobs = ref(false);
let loadSavedJobsPromise: Promise<void> | null = null;

export function useJobs(source: Ref<JobOpportunity[]>) {
  async function loadSavedJobs(force = false): Promise<void> {
    if (!force && loadSavedJobsPromise) {
      return loadSavedJobsPromise;
    }
    loadingSavedJobs.value = true;
    loadSavedJobsPromise = fetchUserSavedJobs()
      .then((payload) => {
        savedJobIds.value = payload.items.map((item) => item.job_id);
      })
      .catch(() => {
        savedJobIds.value = [];
      })
      .finally(() => {
        loadingSavedJobs.value = false;
      });
    return loadSavedJobsPromise;
  }

  void loadSavedJobs();

  const query = ref("");
  const decision = ref<"all" | "APPLY_NOW" | "REVIEW" | "IGNORE">("all");
  const minScore = ref(0);

  async function toggleSavedJob(jobId: string): Promise<void> {
    const wasSaved = savedJobIds.value.includes(jobId);
    const previous = [...savedJobIds.value];
    savedJobIds.value = wasSaved ? savedJobIds.value.filter((value) => value !== jobId) : [jobId, ...savedJobIds.value];
    try {
      if (wasSaved) {
        await deleteUserSavedJob(jobId);
      } else {
        await saveUserSavedJob(jobId);
      }
    } catch (error) {
      savedJobIds.value = previous;
      throw error;
    }
  }

  function isSavedJob(jobId: string): boolean {
    return savedJobIds.value.includes(jobId);
  }

  const filteredJobs = computed(() =>
    source.value.filter((job) => {
      const matchesQuery =
        !query.value ||
        `${job.title} ${job.company} ${job.location} ${job.remote_policy}`.toLowerCase().includes(query.value.toLowerCase());
      const matchesDecision = decision.value === "all" || job.decision === decision.value;
      const matchesScore = job.match_score >= minScore.value;
      return matchesQuery && matchesDecision && matchesScore;
    }),
  );

  const savedJobs = computed(() => source.value.filter((job) => savedJobIds.value.includes(job.id)));

  return {
    query,
    decision,
    minScore,
    filteredJobs,
    savedJobs,
    savedJobIds,
    loadingSavedJobs,
    loadSavedJobs,
    toggleSavedJob,
    isSavedJob,
  };
}
