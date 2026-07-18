<script setup lang="ts">
import { onMounted, ref } from "vue";

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
import { formatFileSize } from "../../utils/format";

const auth = useAuth();
const { pushToast } = useToast();

const resumes = ref<ResumeAsset[]>([]);
const loading = ref(true);
const uploading = ref(false);
const error = ref<string | null>(null);

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
      <AppGrid columns="3">
        <AppCard v-for="resume in resumes" :key="resume.id" :title="resume.display_name" :subtitle="resume.role_focus || 'General profile'" class="resume-card">
          <div class="resume-card__meta">
            <AppBadge tone="primary">{{ formatFileSize(resume.file_size_bytes) }}</AppBadge>
            <AppBadge tone="neutral">{{ resume.mime_type }}</AppBadge>
          </div>
          <div class="resume-card__skills">
            <AppBadge v-for="skill in resume.extracted_skills.slice(0, 8)" :key="skill" tone="info" size="sm">
              {{ skill }}
            </AppBadge>
          </div>
          <p class="resume-card__preview">{{ resume.extracted_text_preview || "Text extraction is still running." }}</p>
        </AppCard>
      </AppGrid>
    </PageSection>
  </AppPage>
</template>

<style scoped>
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

.resume-card__meta,
.resume-card__skills {
  display: flex;
  flex-wrap: wrap;
  gap: var(--content-gap);
}

.resume-card__preview {
  margin: 0;
  color: var(--color-text-muted);
  font-size: var(--type-small);
  line-height: 1.55;
}
</style>
