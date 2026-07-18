<script setup lang="ts">
import { computed } from "vue";
import { RouterLink, useRoute } from "vue-router";

import AppBadge from "../ui/AppBadge.vue";
import AppTooltip from "../ui/AppTooltip.vue";
import type { SidebarItem } from "../../types";
import { iconMap } from "../../utils/icons";

const props = defineProps<{
  item: SidebarItem;
  collapsed: boolean;
}>();

const route = useRoute();
const icon = computed(() => iconMap[props.item.icon]);
const active = computed(() => route.path === props.item.to);
</script>

<template>
  <AppTooltip :text="item.label" :disabled="!collapsed">
    <RouterLink class="sidebar-item" :class="{ 'sidebar-item--active': active }" :to="item.to">
      <component :is="icon" />
      <span v-if="!collapsed" class="sidebar-item__label">{{ item.label }}</span>
      <AppBadge v-if="item.badge && !collapsed" tone="info" size="sm">{{ item.badge }}</AppBadge>
    </RouterLink>
  </AppTooltip>
</template>

<style scoped>
.sidebar-item {
  display: flex;
  align-items: center;
  gap: var(--content-gap);
  min-height: 48px;
  padding: 0 var(--content-gap);
  border-radius: 1rem;
  color: var(--sidebar-text);
  transition:
    background var(--transition-fast),
    color var(--transition-fast);
}

.sidebar-item :deep(svg) {
  width: 20px;
  height: 20px;
}

.sidebar-item:hover {
  background: rgba(255, 255, 255, 0.08);
}

.sidebar-item--active {
  background: var(--sidebar-active);
  color: var(--sidebar-active-text);
  box-shadow: 0 18px 42px rgba(37, 99, 255, 0.28);
}

.sidebar-item__label {
  flex: 1;
  font-weight: 600;
}
</style>
