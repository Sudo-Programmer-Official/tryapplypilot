<script setup lang="ts">
import { RouterView } from "vue-router";

import AppShell from "../../components/layout/AppShell.vue";
import { userNavigation } from "../../config/navigation";
</script>

<template>
  <AppShell
    :navigation="userNavigation"
    footer-title="User Workspace"
    footer-body="Resume-driven job alerts and onboarding status in one place."
    logout-route="/auth/login"
  >
    <RouterView />
  </AppShell>
</template>
