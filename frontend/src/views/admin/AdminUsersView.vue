<script setup lang="ts">
import { onMounted, ref } from "vue";

import AppPage from "../../components/layout/AppPage.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppEmptyState from "../../components/ui/AppEmptyState.vue";
import AppTable from "../../components/ui/AppTable.vue";
import { fetchAdminUsers } from "../../api/auth.api";
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
  <AppPage>
    <PageHeader title="Users" description="Inspect account setup, role assignment, and private notification readiness." />

    <AppEmptyState v-if="error" title="Users unavailable" :description="error" />

    <AppCard v-else title="Accounts" :subtitle="loading ? 'Loading users...' : `${users.length} user accounts loaded.`">
      <AppTable :columns="columns" :has-rows="users.length > 0" empty-message="No users found.">
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
  </AppPage>
</template>
