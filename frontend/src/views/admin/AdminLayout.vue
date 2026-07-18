<script setup lang="ts">
import { RouterView } from "vue-router";

import AppShell from "../../components/layout/AppShell.vue";
import { adminNavigation } from "../../config/navigation";
</script>

<template>
  <AppShell
    :navigation="adminNavigation"
    :admin-badge="true"
    footer-title="Admin Console"
    footer-body="Connector health, catalog controls, and user operations."
    logout-route="/admin/login"
  >
    <RouterView />
  </AppShell>
</template>
