import { computed, ref, type Ref } from "vue";

import { deleteUserSavedJob, fetchUserSavedJobs, saveUserSavedJob } from "../api/user.api";
import type { JobOpportunity, MatchDecision } from "../types";

export type JobDecisionFilter = "all" | MatchDecision;
export type JobQueueFilter = "all" | "saved" | "APPLY_NOW" | "REVIEW";
export type JobSortOption = "highest_match" | "newest" | "company" | "recently_updated";

type UseJobsOptions = {
  initialQuery?: string;
};

const savedJobIds = ref<string[]>([]);
const loadingSavedJobs = ref(false);
let loadSavedJobsPromise: Promise<void> | null = null;

export function useJobs(source: Ref<JobOpportunity[]>, options: UseJobsOptions = {}) {
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

  const query = ref(options.initialQuery ?? "");
  const decision = ref<JobDecisionFilter>("all");
  const freshnessHours = ref<number | "all">("all");
  const minScore = ref(0);
  const sortBy = ref<JobSortOption>("highest_match");
  const activeQueue = ref<JobQueueFilter>("all");
  const savedJobIdSet = computed(() => new Set(savedJobIds.value));

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
    return savedJobIdSet.value.has(jobId);
  }

  const baseFilteredJobs = computed(() =>
    source.value.filter((job) => {
      const normalizedQuery = query.value.trim().toLowerCase();
      const matchesQuery =
        !normalizedQuery ||
        `${job.title} ${job.company} ${job.location} ${job.country_display} ${job.remote_policy} ${job.source} ${job.why.join(" ")} ${job.recommendation}`
          .toLowerCase()
          .includes(normalizedQuery);
      const matchesDecision = decision.value === "all" || job.decision === decision.value;
      const matchesFreshness = freshnessHours.value === "all" || job.posted_minutes_ago <= freshnessHours.value * 60;
      const matchesScore = job.match_score >= minScore.value;
      return matchesQuery && matchesDecision && matchesFreshness && matchesScore;
    }),
  );

  function sortJobs(items: JobOpportunity[]): JobOpportunity[] {
    const jobs = [...items];
    jobs.sort((left, right) => {
      if (sortBy.value === "newest" || sortBy.value === "recently_updated") {
        return left.posted_minutes_ago - right.posted_minutes_ago || right.match_score - left.match_score;
      }
      if (sortBy.value === "company") {
        return left.company.localeCompare(right.company) || right.match_score - left.match_score;
      }
      return right.match_score - left.match_score || left.posted_minutes_ago - right.posted_minutes_ago;
    });
    return jobs;
  }

  const queueCounts = computed(() => {
    const jobs = baseFilteredJobs.value;
    return {
      all: jobs.length,
      applyNow: jobs.filter((job) => job.decision === "APPLY_NOW").length,
      review: jobs.filter((job) => job.decision === "REVIEW").length,
      saved: jobs.filter((job) => savedJobIdSet.value.has(job.id)).length,
    };
  });

  const filteredJobs = computed(() => {
    const queuedJobs = baseFilteredJobs.value.filter((job) => {
      if (activeQueue.value === "saved") {
        return savedJobIdSet.value.has(job.id);
      }
      if (activeQueue.value === "all") {
        return true;
      }
      return job.decision === activeQueue.value;
    });
    return sortJobs(queuedJobs);
  });

  const savedJobs = computed(() => source.value.filter((job) => savedJobIdSet.value.has(job.id)));

  return {
    query,
    decision,
    freshnessHours,
    minScore,
    sortBy,
    activeQueue,
    queueCounts,
    baseFilteredJobs,
    filteredJobs,
    savedJobs,
    savedJobIds,
    loadingSavedJobs,
    loadSavedJobs,
    toggleSavedJob,
    isSavedJob,
  };
}
