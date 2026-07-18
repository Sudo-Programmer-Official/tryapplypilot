<script setup lang="ts">
import { computed } from "vue";

import AppCard from "../ui/AppCard.vue";
import AppProgress from "../ui/AppProgress.vue";
import type { OnboardingStep } from "../../types";

const props = defineProps<{
  progress: number;
  steps: OnboardingStep[];
}>();

const completedSteps = computed(() => props.steps.filter((step) => step.completed).length);
</script>

<template>
  <AppCard
    title="Setup Progress"
    subtitle="Finish the remaining steps to unlock stronger job matching and private alert delivery."
  >
    <div class="setup-progress">
      <div class="setup-progress__meter">
        <AppProgress :value="progress" label="Complete" />
        <p class="setup-progress__summary">{{ completedSteps }} of {{ steps.length }} steps completed</p>
      </div>
      <ul class="setup-progress__steps list-reset">
        <li v-for="step in steps" :key="step.id" :class="{ 'setup-progress__step--done': step.completed }">
          <span class="setup-progress__mark">{{ step.completed ? "✓" : "○" }}</span>
          <span class="setup-progress__copy">
            <span class="setup-progress__step-title">{{ step.label }}</span>
            <span class="setup-progress__step-state">{{ step.completed ? "Complete" : "Pending" }}</span>
          </span>
        </li>
      </ul>
    </div>
  </AppCard>
</template>

<style scoped>
.setup-progress {
  display: grid;
  grid-template-columns: minmax(160px, auto) minmax(0, 1fr);
  gap: var(--space-6);
  align-items: start;
}

.setup-progress__meter {
  display: grid;
  justify-items: center;
  gap: var(--space-3);
}

.setup-progress__summary {
  margin: 0;
  color: var(--color-text-muted);
  font-size: var(--type-small);
  text-align: center;
}

.setup-progress__steps {
  display: grid;
  gap: var(--space-3);
}

.setup-progress__steps li {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: var(--space-3);
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface-elevated);
  color: var(--color-text-muted);
}

.setup-progress__step--done {
  color: var(--color-text);
  border-color: rgba(34, 179, 91, 0.2);
  background: linear-gradient(180deg, rgba(34, 179, 91, 0.06), rgba(255, 255, 255, 0.92));
}

.setup-progress__mark {
  display: grid;
  place-items: center;
  width: 1.5rem;
  height: 1.5rem;
  margin-top: 0;
  border-radius: 50%;
  color: var(--color-success);
  background: rgba(34, 179, 91, 0.12);
  font-weight: 700;
}

.setup-progress__copy {
  display: grid;
  gap: var(--space-1);
}

.setup-progress__step-title {
  font-weight: 600;
}

.setup-progress__step-state {
  color: var(--color-text-muted);
  font-size: var(--type-caption);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

@media (max-width: 767px) {
  .setup-progress {
    grid-template-columns: 1fr;
    justify-items: center;
  }
}
</style>
