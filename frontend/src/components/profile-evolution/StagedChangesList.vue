<script setup lang="ts">
import AppCard from "../ui/AppCard.vue";
import AppEmptyState from "../ui/AppEmptyState.vue";
import AppSkeleton from "../ui/AppSkeleton.vue";
import type { ProfileEvolutionChangeItem } from "../../types";
import ChangeReviewCard from "./ChangeReviewCard.vue";

defineProps<{
  loading: boolean;
  items: ProfileEvolutionChangeItem[];
  reviewNotes: Record<string, string>;
  activeDecisionId: string;
}>();

const emit = defineEmits<{
  "update:reviewNote": [versionId: string, value: string];
  approve: [versionId: string];
  reject: [versionId: string];
}>();
</script>

<template>
  <AppCard
    class="profile-panel profile-evolution-panel"
    title="Suggested updates"
    subtitle="Review each evidence-backed change before it becomes part of your canonical career profile."
  >
    <div v-if="loading" class="profile-evolution-loading">
      <AppSkeleton class="profile-evolution-skeleton profile-evolution-skeleton--panel" />
      <AppSkeleton class="profile-evolution-skeleton profile-evolution-skeleton--panel" />
    </div>

    <AppEmptyState
      v-else-if="items.length === 0"
      title="No staged changes"
      description="Suggested profile updates will appear here after you answer a profile evolution question."
    />

    <div v-else class="profile-review-list">
      <ChangeReviewCard
        v-for="item in items"
        :key="item.version.id"
        :item="item"
        :review-note="reviewNotes[item.version.id] ?? ''"
        :active="activeDecisionId === item.version.id"
        @update:review-note="emit('update:reviewNote', item.version.id, $event)"
        @approve="emit('approve', item.version.id)"
        @reject="emit('reject', item.version.id)"
      />
    </div>
  </AppCard>
</template>

<style scoped>
.profile-evolution-loading,
.profile-review-list {
  display: grid;
  gap: var(--space-5);
}

.profile-evolution-skeleton {
  min-height: 1rem;
}

.profile-evolution-skeleton--panel {
  min-height: 12rem;
  border-radius: 1.5rem;
}
</style>
