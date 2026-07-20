<script setup lang="ts">
defineProps<{
  modelValue: string;
  label?: string;
  placeholder?: string;
  disabled?: boolean;
  hint?: string;
  readonly?: boolean;
  rows?: number;
}>();

defineEmits<{
  (event: "update:modelValue", value: string): void;
}>();
</script>

<template>
  <label class="app-field">
    <span v-if="label" class="app-field__label">{{ label }}</span>
    <textarea
      class="app-textarea"
      :value="modelValue"
      :rows="rows ?? 4"
      :placeholder="placeholder"
      :disabled="disabled"
      :readonly="readonly"
      @input="$emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
    />
    <span v-if="hint" class="app-field__hint">{{ hint }}</span>
  </label>
</template>

<style scoped>
.app-field {
  display: grid;
  gap: var(--field-gap);
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

.app-textarea {
  width: 100%;
  min-height: 3.25rem;
  padding: var(--input-padding-y) var(--input-padding-x);
  border: 1px solid var(--color-border);
  border-radius: 1rem;
  background: var(--color-surface-elevated);
  color: var(--color-text);
  resize: vertical;
  font: inherit;
  line-height: 1.6;
  transition:
    border-color var(--transition-fast),
    box-shadow var(--transition-fast),
    background var(--transition-fast);
}

.app-textarea::placeholder {
  color: var(--color-text-muted);
}

.app-textarea:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 4px rgba(37, 99, 255, 0.12);
}
</style>
