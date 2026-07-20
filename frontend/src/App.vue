<script setup lang="ts">
import { onMounted, onBeforeUnmount } from "vue";
import { useRouter } from "vue-router";

import AppToast from "./components/ui/AppToast.vue";
import { useAuth } from "./composables/useAuth";
import { AUTH_SESSION_CLEARED_EVENT } from "./api/client";
import { useTheme } from "./composables/useTheme";

useTheme().init();
const auth = useAuth();
const router = useRouter();

function redirectForExpiredSession(): void {
  const currentPath = router.currentRoute.value.path;
  if (currentPath === "/" || currentPath.startsWith("/auth/")) {
    return;
  }
  if (currentPath.startsWith("/admin")) {
    void router.replace("/admin/login");
    return;
  }
  void router.replace("/auth/login");
}

onMounted(() => {
  window.addEventListener(AUTH_SESSION_CLEARED_EVENT, redirectForExpiredSession);
});

onBeforeUnmount(() => {
  window.removeEventListener(AUTH_SESSION_CLEARED_EVENT, redirectForExpiredSession);
});

auth.init();
</script>

<template>
  <RouterView />
  <AppToast />
</template>
