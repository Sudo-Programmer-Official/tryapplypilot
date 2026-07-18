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
  font-size: 0.84rem;
  font-weight: 600;
}

.app-select {
  min-height: 44px;
  padding: 0.75rem 0.9rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface-elevated);
  color: var(--color-text);
}
</style>
