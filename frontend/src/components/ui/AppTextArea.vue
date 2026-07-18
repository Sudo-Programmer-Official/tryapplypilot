<script setup lang="ts">
defineProps<{
  modelValue: string;
  label?: string;
  placeholder?: string;
  disabled?: boolean;
  hint?: string;
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
      @input="$emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
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
  font-size: 0.84rem;
  font-weight: 600;
  color: var(--color-text);
}

.app-field__hint {
  color: var(--color-text-muted);
  font-size: 0.78rem;
}

.app-textarea {
  width: 100%;
  padding: 0.75rem 0.9rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface-elevated);
  color: var(--color-text);
  resize: vertical;
  font: inherit;
}

.app-textarea::placeholder {
  color: var(--color-text-muted);
}
</style>
