<script setup lang="ts">
defineProps<{
  modelValue: boolean;
  label: string;
  disabled?: boolean;
}>();

defineEmits<{
  (event: "update:modelValue", value: boolean): void;
}>();
</script>

<template>
  <label class="app-checkbox">
    <input
      class="app-checkbox__input"
      type="checkbox"
      :checked="modelValue"
      :disabled="disabled"
      @change="$emit('update:modelValue', ($event.target as HTMLInputElement).checked)"
    />
    <span class="app-checkbox__box" aria-hidden="true" />
    <span>{{ label }}</span>
  </label>
</template>

<style scoped>
.app-checkbox {
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
  color: var(--color-text);
}

.app-checkbox__input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.app-checkbox__box {
  width: 1.15rem;
  height: 1.15rem;
  border-radius: 0.35rem;
  border: 1px solid var(--color-border-strong);
  background: var(--color-surface-elevated);
  transition: background var(--transition-fast);
}

.app-checkbox__input:checked + .app-checkbox__box {
  background: var(--color-primary);
  border-color: var(--color-primary);
  box-shadow: inset 0 0 0 3px white;
}
</style>
