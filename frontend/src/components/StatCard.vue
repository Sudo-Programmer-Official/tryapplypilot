<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    label: string;
    value: string | number;
    detail: string;
    tone?: "ink" | "moss" | "clay" | "brass";
  }>(),
  {
    tone: "ink",
  },
);

const toneClassMap = {
  ink: "text-ink",
  moss: "text-moss",
  clay: "text-clay",
  brass: "text-brass",
} as const;
</script>

<template>
  <article class="panel p-5">
    <p class="subtle-label">{{ props.label }}</p>
    <div class="mt-4 flex items-end justify-between gap-4">
      <p :class="['metric-value', toneClassMap[props.tone]]">{{ props.value }}</p>
      <span class="chip">{{ props.detail }}</span>
    </div>
  </article>
</template>

