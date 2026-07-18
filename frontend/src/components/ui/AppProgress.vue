<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    value: number;
    size?: number;
    stroke?: number;
    label?: string;
  }>(),
  {
    size: 156,
    stroke: 12,
    label: "",
  },
);

const circleStyle = computed(() => ({
  width: `${props.size}px`,
  height: `${props.size}px`,
  background: `conic-gradient(var(--color-success) ${props.value}%, var(--color-surface-muted) ${props.value}% 100%)`,
  padding: `${props.stroke}px`,
}));
</script>

<template>
  <div class="app-progress" :style="circleStyle">
    <div class="app-progress__inner">
      <strong>{{ value }}%</strong>
      <span v-if="label">{{ label }}</span>
    </div>
  </div>
</template>

<style scoped>
.app-progress {
  display: inline-grid;
  place-items: center;
  border-radius: 50%;
}

.app-progress__inner {
  display: grid;
  place-items: center;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: var(--color-surface-elevated);
  text-align: center;
}

.app-progress__inner strong {
  font-family: var(--font-display);
  font-size: var(--type-heading);
  line-height: 1;
}

.app-progress__inner span {
  color: var(--color-text-muted);
  font-size: var(--type-caption);
}
</style>
