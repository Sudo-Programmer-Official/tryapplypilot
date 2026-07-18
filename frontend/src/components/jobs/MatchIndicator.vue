<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  score: number;
}>();

const style = computed(() => ({
  background: `conic-gradient(var(--color-success) ${props.score}%, var(--color-surface-muted) ${props.score}% 100%)`,
}));
</script>

<template>
  <div class="match-indicator" :style="style">
    <div class="match-indicator__inner">
      <strong>{{ score }}%</strong>
      <span>Match</span>
    </div>
  </div>
</template>

<style scoped>
.match-indicator {
  width: 4rem;
  height: 4rem;
  padding: 0.35rem;
  border-radius: 50%;
}

.match-indicator__inner {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--color-surface-elevated);
  text-align: center;
}

.match-indicator__inner strong {
  font-family: var(--font-display);
  font-size: var(--type-small);
  line-height: 1;
}

.match-indicator__inner span {
  color: var(--color-text-muted);
  font-size: var(--type-caption);
}
</style>
