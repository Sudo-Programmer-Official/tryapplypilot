<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    variant?: "primary" | "secondary" | "ghost" | "danger";
    size?: "sm" | "md" | "lg";
    block?: boolean;
    disabled?: boolean;
    type?: "button" | "submit" | "reset";
    href?: string;
    target?: string;
    rel?: string;
  }>(),
  {
    variant: "primary",
    size: "md",
    block: false,
    disabled: false,
    type: "button",
    href: undefined,
    target: undefined,
    rel: undefined,
  },
);

const classes = computed(() => [
  "app-button",
  `app-button--${props.variant}`,
  `app-button--${props.size}`,
  props.block ? "app-button--block" : "",
]);
</script>

<template>
  <component :is="href ? 'a' : 'button'" :type="href ? undefined : type" :href="href" :target="target" :rel="rel" :disabled="href ? undefined : disabled" :class="classes">
    <slot />
  </component>
</template>

<style scoped>
.app-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  min-height: 44px;
  padding: 0 var(--space-5);
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  font-weight: 600;
  transition:
    transform var(--transition-fast),
    background var(--transition-fast),
    border-color var(--transition-fast),
    color var(--transition-fast),
    box-shadow var(--transition-fast);
  cursor: pointer;
}

.app-button:hover:not(:disabled) {
  transform: translateY(-1px);
}

.app-button:disabled {
  opacity: 0.56;
  cursor: not-allowed;
}

.app-button--block {
  width: 100%;
}

.app-button--primary {
  background: var(--color-primary);
  color: white;
  box-shadow: var(--shadow-sm);
}

.app-button--primary:hover:not(:disabled) {
  background: var(--color-primary-hover);
}

.app-button--secondary {
  background: var(--color-surface-muted);
  border-color: var(--color-border);
  color: var(--color-text);
}

.app-button--ghost {
  background: transparent;
  border-color: var(--color-border);
  color: var(--color-text);
}

.app-button--danger {
  background: var(--color-danger-soft);
  border-color: transparent;
  color: var(--color-danger);
}

.app-button--sm {
  min-height: 40px;
  padding: 0 var(--space-4);
  font-size: 0.875rem;
}

.app-button--lg {
  min-height: 48px;
  padding: 0 var(--space-6);
}
</style>
