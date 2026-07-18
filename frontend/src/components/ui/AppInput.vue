<script setup lang="ts">
defineProps<{
  modelValue: string | number;
  label?: string;
  placeholder?: string;
  type?: string;
  disabled?: boolean;
  hint?: string;
  min?: number;
  max?: number;
  step?: number;
}>();

defineEmits<{
  (event: "update:modelValue", value: string | number): void;
}>();
</script>

<template>
  <label class="app-field">
    <span v-if="label" class="app-field__label">{{ label }}</span>
    <input
      class="app-input"
      :value="modelValue"
      :type="type ?? 'text'"
      :placeholder="placeholder"
      :disabled="disabled"
      :min="min"
      :max="max"
      :step="step"
      @input="
        $emit(
          'update:modelValue',
          (type ?? 'text') === 'number'
            ? Number(($event.target as HTMLInputElement).value)
            : ($event.target as HTMLInputElement).value,
        )
      "
    />
    <span v-if="hint" class="app-field__hint">{{ hint }}</span>
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
  color: var(--color-text);
}

.app-field__hint {
  color: var(--color-text-muted);
  font-size: var(--type-caption);
}

.app-input {
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

.app-input::placeholder {
  color: var(--color-text-muted);
}

.app-input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 4px rgba(37, 99, 255, 0.12);
}
</style>
