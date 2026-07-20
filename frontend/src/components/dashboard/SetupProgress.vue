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
    class="setup-progress-card"
    title="Setup Progress"
    subtitle="Finish the remaining steps to unlock stronger job matching and private alert delivery."
  >
    <div class="setup-progress">
      <div class="setup-progress__meter">
        <div class="setup-progress__meter-shell">
          <AppProgress :value="progress" :size="180" :stroke="14" label="Complete" />
        </div>
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
.setup-progress-card :deep(.app-card__header) {
  padding: clamp(var(--space-6), 3vw, 2.25rem) clamp(var(--space-6), 4vw, 2.5rem) 0;
}

.setup-progress-card :deep(.app-card__header-copy) {
  gap: var(--space-3);
}

.setup-progress-card :deep(.app-card__title) {
  font-size: clamp(1.625rem, 2.3vw, 2rem);
  letter-spacing: -0.03em;
}

.setup-progress-card :deep(.app-card__subtitle) {
  max-width: 42ch;
  font-size: 0.98rem;
}

.setup-progress-card :deep(.app-card__body) {
  padding: var(--space-6) clamp(var(--space-6), 4vw, 2.5rem) clamp(var(--space-6), 4vw, 2.25rem);
}

.setup-progress {
  display: grid;
  grid-template-columns: minmax(220px, 0.9fr) minmax(0, 1.1fr);
  gap: clamp(var(--space-6), 3vw, var(--space-8));
  align-items: start;
}

.setup-progress__meter {
  display: grid;
  justify-items: center;
  gap: var(--space-4);
}

.setup-progress__meter-shell {
  display: grid;
  place-items: center;
  width: 100%;
  padding: var(--space-4);
  border-radius: calc(var(--radius-lg) + var(--space-1));
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.88), rgba(238, 243, 251, 0.92));
  border: 1px solid rgba(15, 29, 58, 0.08);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72);
}

.setup-progress__summary {
  margin: 0;
  color: var(--color-text-muted);
  font-size: 0.95rem;
  line-height: 1.55;
  text-align: center;
}

.setup-progress__steps {
  display: grid;
  gap: var(--space-4);
}

.setup-progress__steps li {
  position: relative;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: var(--space-4);
  align-items: center;
  padding: var(--space-5);
  border: 1px solid rgba(15, 29, 58, 0.09);
  border-radius: var(--radius-lg);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(246, 249, 253, 0.96));
  color: var(--color-text-muted);
  box-shadow: 0 14px 30px rgba(15, 29, 58, 0.05);
  transition:
    transform var(--transition-base),
    box-shadow var(--transition-base),
    border-color var(--transition-base);
}

.setup-progress__steps li::before {
  content: "";
  position: absolute;
  left: 0;
  top: var(--space-4);
  bottom: var(--space-4);
  width: 4px;
  border-radius: var(--radius-pill);
  background: rgba(102, 114, 141, 0.22);
}

.setup-progress__steps li:hover {
  transform: translateY(-2px);
  box-shadow: 0 20px 38px rgba(15, 29, 58, 0.08);
}

.setup-progress__step--done {
  color: var(--color-text);
  border-color: rgba(34, 179, 91, 0.16);
  background: linear-gradient(180deg, rgba(34, 179, 91, 0.08), rgba(255, 255, 255, 0.96));
}

.setup-progress__step--done::before {
  background: linear-gradient(180deg, rgba(34, 179, 91, 0.92), rgba(36, 160, 237, 0.55));
}

.setup-progress__mark {
  display: grid;
  place-items: center;
  width: 3rem;
  height: 3rem;
  margin-top: 0;
  border-radius: 50%;
  color: var(--color-success);
  background: rgba(34, 179, 91, 0.12);
  box-shadow: inset 0 0 0 1px rgba(34, 179, 91, 0.08);
  font-weight: 700;
  font-size: 1.4rem;
}

.setup-progress__copy {
  display: grid;
  gap: var(--space-2);
}

.setup-progress__step-title {
  font-size: 1.05rem;
  font-weight: 600;
  line-height: 1.35;
}

.setup-progress__step-state {
  color: var(--color-text-muted);
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

@media (max-width: 767px) {
  .setup-progress-card :deep(.app-card__header) {
    padding: var(--space-5) var(--space-5) 0;
  }

  .setup-progress-card :deep(.app-card__body) {
    padding: var(--space-5);
  }

  .setup-progress {
    grid-template-columns: 1fr;
    justify-items: center;
  }

  .setup-progress__meter-shell {
    padding: var(--space-3);
  }

  .setup-progress__steps {
    width: 100%;
  }
}
</style>
