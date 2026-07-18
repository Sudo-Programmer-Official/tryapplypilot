<script setup lang="ts">
import { computed } from "vue";

import AppBadge from "../ui/AppBadge.vue";
import AppButton from "../ui/AppButton.vue";
import AppCard from "../ui/AppCard.vue";
import AppTable from "../ui/AppTable.vue";
import type { CompanyRequest, TableColumn } from "../../types";
import { formatDate } from "../../utils/format";

const props = defineProps<{
  requests: CompanyRequest[];
  showActions?: boolean;
}>();

defineEmits<{
  (event: "approve", item: CompanyRequest): void;
  (event: "reject", item: CompanyRequest): void;
  (event: "edit", item: CompanyRequest): void;
  (event: "merge", item: CompanyRequest): void;
}>();

const columns = computed<TableColumn[]>(() => [
  { key: "company", label: "Company" },
  { key: "requestedBy", label: "Requested By" },
  { key: "connector", label: "Suggested Connector" },
  { key: "createdAt", label: "Requested On" },
  ...(props.showActions ? [{ key: "actions", label: "Actions" }] : []),
]);
</script>

<template>
  <AppCard title="Pending Company Requests">
    <AppTable :columns="columns" :has-rows="requests.length > 0" empty-message="No company requests right now.">
      <tr v-for="request in requests" :key="request.id">
        <td>
          <strong>{{ request.company_name }}</strong>
          <p>{{ request.notes || "No additional notes." }}</p>
        </td>
        <td>{{ request.requester_email }}</td>
        <td><AppBadge tone="info">{{ request.connector_suggestion || "Unspecified" }}</AppBadge></td>
        <td>{{ formatDate(request.created_at) }}</td>
        <td v-if="showActions">
          <div class="request-actions">
            <AppButton size="sm" variant="secondary" @click="$emit('edit', request)">Edit</AppButton>
            <AppButton size="sm" @click="$emit('approve', request)">Approve</AppButton>
            <AppButton size="sm" variant="danger" @click="$emit('reject', request)">Reject</AppButton>
            <AppButton size="sm" variant="ghost" @click="$emit('merge', request)">Merge</AppButton>
          </div>
        </td>
      </tr>
    </AppTable>
  </AppCard>
</template>

<style scoped>
td {
  padding: var(--space-4) 0;
  border-top: 1px solid var(--color-border);
  vertical-align: top;
}

td p {
  margin: var(--space-1) 0 0;
  color: var(--color-text-muted);
}

.request-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
</style>
