<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import PageSection from "../../components/layout/PageSection.vue";
import AppBadge from "../../components/ui/AppBadge.vue";
import AppButton from "../../components/ui/AppButton.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppEmptyState from "../../components/ui/AppEmptyState.vue";
import { fetchUserResumes, uploadUserResume } from "../../api/resumes.api";
import { useAuth } from "../../composables/useAuth";
import { useToast } from "../../composables/useToast";
import type { ResumeAsset } from "../../types";
import { formatDate, formatFileSize } from "../../utils/format";

const auth = useAuth();
const { pushToast } = useToast();

const resumes = ref<ResumeAsset[]>([]);
const loading = ref(true);
const uploading = ref(false);
const error = ref<string | null>(null);

const uploadedLabel = computed(() => {
  if (uploading.value) {
    return "Uploading...";
  }
  return resumes.value.length > 0 ? `${resumes.value.length} resume${resumes.value.length === 1 ? "" : "s"} ready` : "Upload your first resume";
});

async function load(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const payload = await fetchUserResumes();
    resumes.value = payload.items;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Failed to load resumes.";
  } finally {
    loading.value = false;
  }
}

async function handleFileChange(event: Event): Promise<void> {
  const file = (event.target as HTMLInputElement).files?.[0];
  if (!file) {
    return;
  }
  uploading.value = true;
  try {
    const payload = await uploadUserResume(file);
    auth.setUser(payload.user);
    await load();
    pushToast("Resume uploaded", `${payload.item.display_name} is ready for matching.`, "success");
  } catch (err) {
    const message = err instanceof Error ? err.message : "Upload failed.";
    pushToast("Resume upload failed", message, "error");
  } finally {
    uploading.value = false;
    (event.target as HTMLInputElement).value = "";
  }
}

onMounted(load);
</script>

<template>
  <AppPage>
    <PageHeader
      title="Resume library"
      description="Upload resume variants so the matching engine has a stronger profile and can recommend the right version later."
    >
      <template #actions>
        <label class="resume-upload">
          <AppButton type="button" :disabled="uploading">
            {{ uploading ? "Uploading..." : "Upload resume" }}
          </AppButton>
          <input type="file" accept=".pdf,.doc,.docx,.txt" :disabled="uploading" @change="handleFileChange" />
        </label>
      </template>
    </PageHeader>

    <PageSection class="resume-summary-section">
      <div class="resume-summary surface-card">
        <div class="resume-summary__copy">
          <strong>{{ resumes.length }}</strong>
          <span>resume variants</span>
        </div>
        <p>{{ uploadedLabel }}</p>
      </div>
    </PageSection>

    <PageSection v-if="error">
      <AppGrid columns="1">
        <AppEmptyState title="Resume library unavailable" :description="error" />
      </AppGrid>
    </PageSection>
    <PageSection v-else-if="!loading && resumes.length === 0">
      <AppGrid columns="1">
        <AppEmptyState
          title="No resumes uploaded"
          description="Upload your first resume to improve matching quality and complete onboarding."
        />
      </AppGrid>
    </PageSection>

    <PageSection v-else>
      <AppGrid columns="3" class="resume-grid">
        <AppCard v-for="resume in resumes" :key="resume.id" :title="resume.display_name" :subtitle="resume.role_focus || 'General profile'" class="resume-card">
          <div class="resume-card__meta">
            <AppBadge tone="primary">{{ formatFileSize(resume.file_size_bytes) }}</AppBadge>
            <AppBadge tone="neutral">{{ resume.mime_type }}</AppBadge>
            <AppBadge tone="neutral">{{ formatDate(resume.created_at) }}</AppBadge>
          </div>
          <div v-if="resume.extracted_skills.length > 0" class="resume-card__skills">
            <AppBadge v-for="skill in resume.extracted_skills.slice(0, 8)" :key="skill" tone="info" size="sm">
              {{ skill }}
            </AppBadge>
          </div>
          <div class="resume-card__preview-shell">
            <p class="resume-card__preview">{{ resume.extracted_text_preview || "Text extraction is still running." }}</p>
          </div>
        </AppCard>
      </AppGrid>
    </PageSection>
  </AppPage>
</template>

<style scoped>
.resume-summary-section {
  padding-top: 0;
  padding-bottom: 0;
}

.resume-summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-5);
}

.resume-summary__copy {
  display: inline-flex;
  align-items: baseline;
  gap: var(--space-3);
}

.resume-summary__copy strong {
  font-family: var(--font-display);
  font-size: clamp(1.5rem, 2vw, 1.85rem);
  line-height: 1;
  letter-spacing: -0.03em;
}

.resume-summary__copy span,
.resume-summary p {
  color: var(--color-text-muted);
  font-size: 0.95rem;
}

.resume-summary p {
  margin: 0;
}

.resume-upload {
  position: relative;
  display: inline-flex;
  align-items: center;
  cursor: pointer;
}

.resume-upload input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.resume-grid {
  align-items: stretch;
}

.resume-card {
  min-height: 100%;
}

.resume-card :deep(.app-card__header) {
  padding: clamp(var(--space-6), 3vw, 2.25rem) clamp(var(--space-6), 4vw, 2.5rem) 0;
}

.resume-card :deep(.app-card__header-copy) {
  gap: var(--space-3);
}

.resume-card :deep(.app-card__title) {
  font-size: clamp(1.35rem, 1.9vw, 1.65rem);
  letter-spacing: -0.03em;
  text-wrap: balance;
}

.resume-card :deep(.app-card__subtitle) {
  max-width: 28ch;
  font-size: 0.95rem;
}

.resume-card :deep(.app-card__body) {
  padding: var(--space-5) clamp(var(--space-6), 4vw, 2.5rem) clamp(var(--space-6), 4vw, 2.25rem);
  gap: var(--space-5);
}

.resume-card__meta,
.resume-card__skills {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.resume-card__meta :deep(.app-badge),
.resume-card__skills :deep(.app-badge) {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
}

.resume-card__preview-shell {
  padding: var(--space-5);
  border: 1px solid rgba(15, 29, 58, 0.08);
  border-radius: var(--radius-lg);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.84), rgba(246, 249, 253, 0.98));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
}

.resume-card__preview {
  margin: 0;
  color: var(--color-text-muted);
  font-size: 0.95rem;
  line-height: 1.7;
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 8;
}

@media (max-width: 1279px) {
  .resume-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 767px) {
  .resume-summary {
    padding: var(--space-4);
  }

  .resume-grid {
    grid-template-columns: 1fr;
  }

  .resume-card :deep(.app-card__header) {
    padding: var(--space-5) var(--space-5) 0;
  }

  .resume-card :deep(.app-card__body) {
    padding: var(--space-5);
  }

  .resume-card__preview-shell {
    padding: var(--space-4);
  }
}
</style>
