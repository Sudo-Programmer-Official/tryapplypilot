<script setup lang="ts">
import AppDrawer from "../ui/AppDrawer.vue";
import AppSidebar from "./AppSidebar.vue";
import type { SidebarItem } from "../../types";

defineProps<{
  open: boolean;
  navigation: SidebarItem[];
  adminBadge?: boolean;
  footerTitle: string;
  footerBody: string;
}>();

defineEmits<{
  (event: "close"): void;
  (event: "toggle-pin"): void;
  (event: "logout"): void;
}>();
</script>

<template>
  <AppDrawer :open="open" title="Navigation" @close="$emit('close')">
    <AppSidebar
      :navigation="navigation"
      :collapsed="false"
      :expanded="true"
      :admin-badge="adminBadge"
      :footer-title="footerTitle"
      :footer-body="footerBody"
      @toggle-pin="$emit('toggle-pin')"
      @logout="$emit('logout')"
      @navigate="$emit('close')"
    />
  </AppDrawer>
</template>
