<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    label: string;
    tone?: "default" | "soft";
    size?: "sm" | "md";
    disabled?: boolean;
    type?: "button" | "submit";
  }>(),
  {
    tone: "default",
    size: "md",
    disabled: false,
    type: "button",
  },
);
</script>

<template>
  <button :type="type" :disabled="disabled" class="app-icon-button" :class="[`app-icon-button--${tone}`, `app-icon-button--${size}`]" :aria-label="label">
    <slot />
  </button>
</template>

<style scoped>
.app-icon-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  color: var(--color-text);
  background: var(--color-surface-elevated);
  cursor: pointer;
  transition:
    border-color var(--transition-fast),
    background var(--transition-fast),
    transform var(--transition-fast);
}

.app-icon-button:hover:not(:disabled) {
  transform: translateY(-1px);
  border-color: var(--color-border-strong);
}

.app-icon-button :deep(svg) {
  width: 18px;
  height: 18px;
}

.app-icon-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.app-icon-button--soft {
  background: var(--color-surface-muted);
}

.app-icon-button--sm {
  width: 36px;
  height: 36px;
  border-radius: 0.875rem;
}

.app-icon-button--sm :deep(svg) {
  width: 16px;
  height: 16px;
}
</style>
