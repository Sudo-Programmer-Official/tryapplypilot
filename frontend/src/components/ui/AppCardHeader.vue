<script setup lang="ts">
defineProps<{
  title?: string;
  subtitle?: string;
}>();
</script>

<template>
  <header class="app-card-header">
    <div class="app-card-header__copy">
      <slot>
        <h3 v-if="title" class="app-card-header__title">{{ title }}</h3>
        <p v-if="subtitle" class="app-card-header__subtitle">{{ subtitle }}</p>
      </slot>
    </div>
    <div v-if="$slots.actions" class="app-card-header__actions">
      <slot name="actions" />
    </div>
  </header>
</template>
