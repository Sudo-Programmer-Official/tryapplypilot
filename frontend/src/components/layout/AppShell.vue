<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";

import AppHeader from "./AppHeader.vue";
import AppSidebar from "./AppSidebar.vue";
import MobileDrawer from "./MobileDrawer.vue";
import { useAuth } from "../../composables/useAuth";
import { useSidebar } from "../../composables/useSidebar";
import { useTheme } from "../../composables/useTheme";
import type { SidebarItem, ThemeMode } from "../../types";

const props = defineProps<{
  navigation: SidebarItem[];
  adminBadge?: boolean;
  footerTitle: string;
  footerBody: string;
  logoutRoute?: string;
}>();

const route = useRoute();
const router = useRouter();
const auth = useAuth();
const sidebar = useSidebar();
const theme = useTheme();

sidebar.init();

const searchValue = computed(() => String(route.query.q ?? ""));
const title = computed(() => String(route.meta.title ?? "Workspace"));
const showHeaderSearch = computed(() => route.meta.headerSearch !== false);

function updateSearch(value: string): void {
  router.replace({
    query: {
      ...route.query,
      q: value || undefined,
    },
  });
}

async function handleLogout(): Promise<void> {
  await auth.logoutCurrentUser();
  await router.push(props.logoutRoute ?? "/auth/login");
}

function updateTheme(value: ThemeMode): void {
  theme.setMode(value);
}
</script>

<template>
  <div class="app-shell" :class="{ 'app-shell--expanded': sidebar.expanded.value }">
    <aside class="app-shell__sidebar hide-tablet" @mouseenter="sidebar.setHovered(true)" @mouseleave="sidebar.setHovered(false)">
      <AppSidebar
        :navigation="navigation"
        :collapsed="sidebar.collapsed.value"
        :expanded="sidebar.expanded.value"
        :admin-badge="adminBadge"
        :footer-title="footerTitle"
        :footer-body="footerBody"
        @toggle-pin="sidebar.togglePin"
        @logout="handleLogout"
        @navigate="sidebar.closeAfterNavigation"
      />
    </aside>

    <MobileDrawer
      :open="sidebar.mobileOpen.value"
      :navigation="navigation"
      :admin-badge="adminBadge"
      :footer-title="footerTitle"
      :footer-body="footerBody"
      @close="sidebar.closeMobile"
      @toggle-pin="sidebar.togglePin"
      @logout="handleLogout"
    />

    <div class="app-shell__content">
      <AppHeader
        :title="title"
        :user="auth.user.value"
        :theme-mode="theme.mode.value"
        :search-value="searchValue"
        :show-search="showHeaderSearch"
        @toggle-sidebar="sidebar.toggleDesktop"
        @update:search="updateSearch"
        @update:theme="updateTheme"
        @logout="handleLogout"
      />
      <main class="app-shell__main page-width">
        <slot />
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: var(--sidebar-collapsed-width) minmax(0, 1fr);
  transition: grid-template-columns var(--transition-slow);
}

.app-shell--expanded {
  grid-template-columns: var(--sidebar-expanded-width) minmax(0, 1fr);
}

.app-shell__sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
}

.app-shell__content {
  padding: 0;
  min-width: 0;
}

.app-shell__main {
  padding: 0 0 var(--page-padding-y);
}

@media (max-width: 1023px) {
  .app-shell,
  .app-shell--expanded {
    grid-template-columns: 1fr;
  }
}
</style>
