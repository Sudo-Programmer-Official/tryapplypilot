<script setup lang="ts">
import { computed } from "vue";
import { LogOut, Pin } from "lucide-vue-next";

import SidebarNavItem from "./SidebarNavItem.vue";
import AppIconButton from "../ui/AppIconButton.vue";
import type { SidebarItem } from "../../types";

const props = defineProps<{
  navigation: SidebarItem[];
  collapsed: boolean;
  expanded: boolean;
  adminBadge?: boolean;
  footerTitle: string;
  footerBody: string;
}>();

defineEmits<{
  (event: "toggle-pin"): void;
  (event: "logout"): void;
  (event: "navigate"): void;
}>();

const showLabels = computed(() => props.expanded);
</script>

<template>
  <aside class="app-sidebar" :class="{ 'app-sidebar--collapsed': !showLabels }">
    <div class="app-sidebar__brand">
      <div class="app-sidebar__brand-mark">◎</div>
      <div v-if="showLabels" class="app-sidebar__brand-copy">
        <div class="app-sidebar__brand-row">
          <strong>TryApplyPilot</strong>
          <span v-if="adminBadge" class="app-sidebar__brand-badge">Admin</span>
        </div>
        <span>Find. Match. Apply.</span>
      </div>
      <AppIconButton v-if="showLabels" label="Pin sidebar" tone="soft" @click="$emit('toggle-pin')">
        <Pin :size="18" />
      </AppIconButton>
    </div>

    <nav class="app-sidebar__nav">
      <SidebarNavItem
        v-for="item in navigation"
        :key="item.to"
        :item="item"
        :collapsed="!showLabels"
        @click="$emit('navigate')"
      />
    </nav>

    <div class="app-sidebar__footer">
      <div class="app-sidebar__status">
        <strong v-if="showLabels">{{ footerTitle }}</strong>
        <span v-if="showLabels">{{ footerBody }}</span>
      </div>
      <button class="app-sidebar__logout" @click="$emit('logout')">
        <LogOut :size="18" />
        <span v-if="showLabels">Logout</span>
      </button>
    </div>
  </aside>
</template>

<style scoped>
.app-sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: var(--space-4);
  gap: var(--space-5);
  color: var(--sidebar-text);
  background: var(--sidebar-background);
  border-right: 1px solid var(--sidebar-border);
}

.app-sidebar--collapsed {
  align-items: center;
}

.app-sidebar__brand {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.app-sidebar__brand-mark {
  display: grid;
  place-items: center;
  width: 2.75rem;
  height: 2.75rem;
  border-radius: 50%;
  background: rgba(37, 99, 255, 0.18);
  color: white;
  font-size: 1.2rem;
}

.app-sidebar__brand-copy {
  flex: 1;
  display: grid;
  gap: var(--space-1);
}

.app-sidebar__brand-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.app-sidebar__brand-row strong {
  font-family: var(--font-display);
  font-size: 1.2rem;
}

.app-sidebar__brand-copy span {
  color: var(--sidebar-text-muted);
  font-size: 0.85rem;
}

.app-sidebar__brand-badge {
  padding: 0.2rem 0.55rem;
  border-radius: var(--radius-pill);
  background: rgba(92, 141, 255, 0.24);
  color: white;
  font-size: 0.72rem;
  font-weight: 700;
}

.app-sidebar__nav {
  display: grid;
  gap: var(--space-2);
  flex: 1;
}

.app-sidebar__footer {
  display: grid;
  gap: var(--space-3);
}

.app-sidebar__status {
  padding: var(--space-4);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.04);
}

.app-sidebar__status strong {
  display: block;
  margin-bottom: var(--space-2);
}

.app-sidebar__status span {
  color: var(--sidebar-text-muted);
  font-size: 0.88rem;
}

.app-sidebar__logout {
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
  min-height: 44px;
  padding: 0 var(--space-4);
  border: 0;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--sidebar-text);
  cursor: pointer;
}

.app-sidebar__logout:hover {
  background: rgba(255, 255, 255, 0.08);
}
</style>
