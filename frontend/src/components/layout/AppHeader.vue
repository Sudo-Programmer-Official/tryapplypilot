<script setup lang="ts">
import { computed, ref } from "vue";
import { Bell, ChevronDown, Menu, Moon, Search, Sun } from "lucide-vue-next";

import AppIconButton from "../ui/AppIconButton.vue";
import AppInput from "../ui/AppInput.vue";
import AppSelect from "../ui/AppSelect.vue";
import type { AuthUser, ThemeMode } from "../../types";
import { getInitials } from "../../utils/format";

const props = defineProps<{
  title: string;
  user: AuthUser | null;
  themeMode: ThemeMode;
  searchValue: string;
  notificationsCount?: number;
}>();

const emit = defineEmits<{
  (event: "toggle-sidebar"): void;
  (event: "update:search", value: string): void;
  (event: "update:theme", value: ThemeMode): void;
  (event: "logout"): void;
}>();

const userMenuOpen = ref(false);
const initials = computed(() => getInitials(props.user?.full_name || props.user?.email || "TP"));
</script>

<template>
  <header class="app-header surface-card">
    <div class="app-header__leading">
      <AppIconButton label="Toggle sidebar" @click="$emit('toggle-sidebar')">
        <Menu :size="20" />
      </AppIconButton>
      <div>
        <h1 class="app-header__title">{{ title }}</h1>
        <p class="app-header__subtitle">Keep the workspace focused and current.</p>
      </div>
    </div>

    <div class="app-header__search hide-mobile">
      <AppInput
        :model-value="searchValue"
        placeholder="Search jobs, companies, roles..."
        @update:model-value="$emit('update:search', String($event))"
      />
    </div>

    <div class="app-header__actions">
      <AppSelect
        class="hide-mobile"
        :model-value="themeMode"
        :options="[
          { label: 'System', value: 'system' },
          { label: 'Light', value: 'light' },
          { label: 'Dark', value: 'dark' },
        ]"
        @update:model-value="$emit('update:theme', $event as ThemeMode)"
      />
      <AppIconButton class="hide-tablet" label="Search">
        <Search :size="18" />
      </AppIconButton>
      <AppIconButton label="Notifications">
        <Bell :size="18" />
        <span v-if="notificationsCount" class="app-header__counter">{{ notificationsCount }}</span>
      </AppIconButton>
      <div class="app-header__user-menu">
        <button class="app-header__user" @click="userMenuOpen = !userMenuOpen">
          <span class="app-header__avatar">{{ initials }}</span>
          <span class="hide-mobile">{{ props.user?.full_name || "Account" }}</span>
          <ChevronDown :size="16" />
        </button>
        <div v-if="userMenuOpen" class="app-header__user-panel surface-card">
          <strong>{{ props.user?.full_name || props.user?.email }}</strong>
          <span>{{ props.user?.role === 'user' ? 'User Workspace' : 'Admin Console' }}</span>
          <button class="app-header__logout" @click="$emit('logout')">Logout</button>
        </div>
      </div>
    </div>
  </header>
</template>

<style scoped>
.app-header {
  position: sticky;
  top: var(--space-4);
  z-index: 20;
  display: grid;
  grid-template-columns: minmax(0, auto) minmax(0, 1fr) auto;
  gap: var(--space-4);
  align-items: center;
  padding: var(--space-4);
}

.app-header__leading {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.app-header__title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.6rem;
  line-height: 1.1;
}

.app-header__subtitle {
  margin: var(--space-1) 0 0;
  color: var(--color-text-muted);
  font-size: 0.92rem;
}

.app-header__actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.app-header__counter {
  position: absolute;
  top: 0.1rem;
  right: 0.1rem;
  display: grid;
  place-items: center;
  min-width: 1.15rem;
  height: 1.15rem;
  border-radius: 50%;
  background: var(--color-danger);
  color: white;
  font-size: 0.65rem;
}

.app-header__user-menu {
  position: relative;
}

.app-header__user {
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
  min-height: 44px;
  padding: 0 var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  background: var(--color-surface-elevated);
  cursor: pointer;
}

.app-header__avatar {
  display: grid;
  place-items: center;
  width: 2.2rem;
  height: 2.2rem;
  border-radius: 50%;
  background: #10244c;
  color: white;
  font-weight: 700;
}

.app-header__user-panel {
  position: absolute;
  right: 0;
  top: calc(100% + var(--space-2));
  min-width: 13rem;
  padding: var(--space-4);
  display: grid;
  gap: var(--space-2);
}

.app-header__user-panel span {
  color: var(--color-text-muted);
  font-size: 0.88rem;
}

.app-header__logout {
  min-height: 40px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface-muted);
  cursor: pointer;
}

@media (max-width: 1023px) {
  .app-header {
    grid-template-columns: 1fr;
  }

  .app-header__search {
    order: 3;
  }
}
</style>
