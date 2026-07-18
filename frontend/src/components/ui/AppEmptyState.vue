<script setup lang="ts">
defineProps<{
  title: string;
  description: string;
}>();
</script>

<template>
  <section class="app-empty surface-card">
    <div class="app-empty__icon">
      <slot name="icon" />
    </div>
    <div>
      <h3>{{ title }}</h3>
      <p>{{ description }}</p>
    </div>
    <div v-if="$slots.actions">
      <slot name="actions" />
    </div>
  </section>
</template>

<style scoped>
.app-empty {
  display: grid;
  place-items: center;
  gap: var(--space-4);
  padding: var(--space-8);
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

.app-empty h3 {
  margin: 0 0 var(--space-2);
  font-family: var(--font-display);
}

.app-empty p {
  margin: 0;
  color: var(--color-text-muted);
}
</style>
