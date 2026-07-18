<script setup lang="ts">
withDefaults(
  defineProps<{
    as?: string;
    width?: "full" | "compact" | "narrow";
    centered?: boolean;
  }>(),
  {
    as: "div",
    width: "full",
    centered: false,
  },
);
</script>

<template>
  <component :is="as" class="app-page" :class="[`app-page--${width}`, { 'app-page--centered': centered }]">
    <slot />
  </component>
</template>
