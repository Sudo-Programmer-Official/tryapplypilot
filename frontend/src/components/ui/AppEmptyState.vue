<script setup lang="ts">
import AppCard from "./AppCard.vue";

defineProps<{
  title: string;
  description: string;
}>();
</script>

<template>
  <AppCard class="app-empty-card" :padded="false">
    <section class="app-empty card-content">
      <div class="app-empty__icon">
        <slot name="icon" />
      </div>
      <div class="app-empty__copy">
        <h3>{{ title }}</h3>
        <p>{{ description }}</p>
      </div>
      <div v-if="$slots.actions">
        <slot name="actions" />
      </div>
    </section>
  </AppCard>
</template>

<style scoped>
.app-empty-card {
  height: auto;
}

.app-empty {
  justify-content: center;
  align-items: center;
  gap: var(--space-4);
  text-align: center;
}

.app-empty__icon {
  width: 3.5rem;
  height: 3.5rem;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: var(--color-surface-muted);
  color: var(--color-text-muted);
}

.app-empty__copy {
  display: grid;
  gap: var(--heading-gap);
}

.app-empty h3 {
  margin: 0;
  font-family: var(--font-display);
}

.app-empty p {
  margin: 0;
  color: var(--color-text-muted);
}
</style>
