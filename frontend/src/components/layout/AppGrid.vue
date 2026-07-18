<script setup lang="ts">
withDefaults(
  defineProps<{
    as?: string;
    columns?: "2" | "3" | "4";
    gap?: "card" | "content";
  }>(),
  {
    as: "div",
    columns: "2",
    gap: "card",
  },
);
</script>

<template>
  <component
    :is="as"
    class="app-grid"
    :class="{ 'app-grid--content': gap === 'content' }"
    :style="{ '--grid-columns': columns }"
  >
    <slot />
  </component>
</template>
