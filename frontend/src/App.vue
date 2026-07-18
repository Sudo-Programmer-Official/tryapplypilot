<script setup lang="ts">
import AppToast from "./components/ui/AppToast.vue";
import { useAuth } from "./composables/useAuth";
import { useTheme } from "./composables/useTheme";

useTheme().init();
useAuth().init();
</script>

<template>
  <RouterView />
  <AppToast />
</template>
