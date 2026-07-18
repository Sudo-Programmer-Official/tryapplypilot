<script setup lang="ts">
import AppCard from "../ui/AppCard.vue";
import AppProgress from "../ui/AppProgress.vue";
import type { OnboardingStep } from "../../types";

defineProps<{
  progress: number;
  steps: OnboardingStep[];
}>();
</script>

<template>
  <AppCard title="Setup Progress">
    <div class="setup-progress">
      <AppProgress :value="progress" label="Complete" />
      <ul class="setup-progress__steps list-reset">
        <li v-for="step in steps" :key="step.id" :class="{ 'setup-progress__step--done': step.completed }">
          <span class="setup-progress__mark">{{ step.completed ? "✓" : "○" }}</span>
          <span>{{ step.label }}</span>
        </li>
      </ul>
    </div>
  </AppCard>
</template>

<style scoped>
.setup-progress {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: var(--space-6);
  align-items: center;
}

.setup-progress__steps {
  display: grid;
  gap: var(--space-3);
}

.setup-progress__steps li {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  color: var(--color-text-muted);
}

.setup-progress__step--done {
  color: var(--color-text);
}

.setup-progress__mark {
  color: var(--color-success);
}

@media (max-width: 767px) {
  .setup-progress {
    grid-template-columns: 1fr;
    justify-items: center;
  }
}
</style>
