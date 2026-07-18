<script setup lang="ts">
defineProps<{
  modelValue: string | number;
  label?: string;
  options: Array<{ label: string; value: string | number }>;
  disabled?: boolean;
}>();

defineEmits<{
  (event: "update:modelValue", value: string): void;
}>();
</script>

<template>
  <label class="app-field">
    <span v-if="label" class="app-field__label">{{ label }}</span>
    <select class="app-select" :value="modelValue" :disabled="disabled" @change="$emit('update:modelValue', ($event.target as HTMLSelectElement).value)">
      <option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option>
    </select>
  </label>
</template>

<style scoped>
.app-field {
  display: grid;
  gap: var(--space-2);
}

.app-field__label {
  font-size: var(--type-small);
  font-weight: 600;
}

.app-select {
  min-height: 3.25rem;
  padding: 0.875rem 1rem;
  border: 1px solid var(--color-border);
  border-radius: 1rem;
  background: var(--color-surface-elevated);
  color: var(--color-text);
  transition:
    border-color var(--transition-fast),
    box-shadow var(--transition-fast),
    background var(--transition-fast);
}

.app-select:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 4px rgba(37, 99, 255, 0.12);
}
</style>
