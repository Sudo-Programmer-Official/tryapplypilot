<script setup lang="ts">
defineProps<{
  eyebrow?: string;
  title?: string;
  description?: string;
}>();
</script>

<template>
  <section class="app-section">
    <div v-if="title || description || eyebrow || $slots.header || $slots.actions" class="app-section__header">
      <div class="app-section__header-row">
        <div>
          <p v-if="eyebrow" class="eyebrow app-section__eyebrow">{{ eyebrow }}</p>
          <slot name="header">
            <h2 v-if="title" class="app-section__title">{{ title }}</h2>
            <p v-if="description" class="app-section__description">{{ description }}</p>
          </slot>
        </div>
        <div v-if="$slots.actions" class="app-section__actions">
          <slot name="actions" />
        </div>
      </div>
    </div>
    <slot />
  </section>
</template>

<style scoped>
.app-section__header-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--content-gap);
}

.app-section__actions {
  display: inline-flex;
  align-items: center;
  gap: var(--content-gap);
}

@media (max-width: 767px) {
  .app-section__header-row {
    flex-direction: column;
  }

  .app-section__actions {
    width: 100%;
  }
}
</style>
