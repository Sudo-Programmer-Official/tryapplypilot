<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { fetchAdminUsers } from "../../api/auth.api";
import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import PageSection from "../../components/layout/PageSection.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppEmptyState from "../../components/ui/AppEmptyState.vue";
import AppSkeleton from "../../components/ui/AppSkeleton.vue";
import AppTable from "../../components/ui/AppTable.vue";
import type { AuthUser, TableColumn } from "../../types";
import { formatDateTime } from "../../utils/format";

const users = ref<AuthUser[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

const columns: TableColumn[] = [
  { key: "name", label: "User" },
  { key: "role", label: "Role" },
  { key: "country", label: "Country" },
  { key: "telegram", label: "Telegram" },
  { key: "onboarding", label: "Setup" },
  { key: "lastLogin", label: "Last Login" },
];

const connectedTelegramCount = computed(() => users.value.filter((user) => Boolean(user.telegram_chat_id)).length);
const completedOnboardingCount = computed(() => users.value.filter((user) => user.onboarding.progress_percent >= 100).length);

async function load(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const payload = await fetchAdminUsers();
    users.value = payload.items;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Failed to load users.";
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <AppPage class="admin-users-page">
    <PageHeader title="Users" description="Inspect account setup, role assignment, and private notification readiness without leaving the admin workspace." />

    <PageSection class="admin-users-page__summary-section">
      <div class="admin-users-summary surface-card">
        <div class="admin-users-summary__item">
          <strong>{{ users.length }}</strong>
          <span>accounts loaded</span>
        </div>
        <div class="admin-users-summary__item">
          <strong>{{ connectedTelegramCount }}</strong>
          <span>telegram connected</span>
        </div>
        <div class="admin-users-summary__item">
          <strong>{{ completedOnboardingCount }}</strong>
          <span>fully onboarded</span>
        </div>
      </div>
    </PageSection>

    <PageSection v-if="error">
      <AppGrid columns="1">
        <AppEmptyState title="Users unavailable" :description="error" />
      </AppGrid>
    </PageSection>

    <PageSection v-else>
      <AppGrid columns="1">
        <AppCard class="admin-users-panel" title="Accounts" :subtitle="loading ? 'Loading users...' : `${users.length} user accounts loaded.`">
          <div v-if="loading" class="admin-users-loading">
            <div v-for="index in 5" :key="index" class="admin-users-loading__row">
              <AppSkeleton class="admin-users-loading__title" />
              <AppSkeleton class="admin-users-loading__meta" />
            </div>
          </div>
          <AppTable v-else :columns="columns" :has-rows="users.length > 0" empty-message="No users found.">
            <tr v-for="user in users" :key="user.id">
              <td class="app-table__copy">
                <strong>{{ user.full_name }}</strong>
                <p>{{ user.email }}</p>
              </td>
              <td>{{ user.role }}</td>
              <td>{{ user.preferences.country ?? user.country }}</td>
              <td>{{ user.telegram_chat_id ? "Connected" : "Pending" }}</td>
              <td>{{ user.onboarding.progress_percent }}%</td>
              <td>{{ formatDateTime(user.last_login_at) }}</td>
            </tr>
          </AppTable>
        </AppCard>
      </AppGrid>
    </PageSection>
  </AppPage>
</template>

<style scoped>
.admin-users-page {
  --page-gap: var(--space-5);
}

.admin-users-page__summary-section {
  margin-bottom: calc(var(--space-2) * -1);
}

.admin-users-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-4);
  padding: clamp(var(--space-4), 2vw, var(--space-5));
}

.admin-users-summary__item,
.admin-users-loading__row {
  display: grid;
  gap: var(--space-2);
}

.admin-users-summary__item strong {
  font-family: var(--font-display);
  font-size: clamp(1.2rem, 1.8vw, 1.45rem);
  letter-spacing: -0.03em;
}

.admin-users-summary__item span {
  color: var(--color-text-muted);
  font-size: 0.92rem;
}

.admin-users-panel :deep(.app-card__header) {
  padding: clamp(var(--space-6), 3vw, 2.25rem) clamp(var(--space-6), 4vw, 2.5rem) 0;
}

.admin-users-panel :deep(.app-card__body) {
  padding: var(--space-5) clamp(var(--space-6), 4vw, 2.5rem) clamp(var(--space-6), 4vw, 2.25rem);
}

.admin-users-loading {
  display: grid;
  gap: var(--space-4);
}

.admin-users-loading__row {
  padding: var(--space-5);
  border: 1px solid rgba(15, 29, 58, 0.08);
  border-radius: var(--radius-lg);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(246, 249, 253, 0.98));
}

.admin-users-loading__title {
  min-height: 1.2rem;
  max-width: 28%;
}

.admin-users-loading__meta {
  min-height: 1rem;
}

@media (max-width: 767px) {
  .admin-users-summary {
    grid-template-columns: 1fr;
  }
}
</style>
