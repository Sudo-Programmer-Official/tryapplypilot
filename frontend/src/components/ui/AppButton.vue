<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    variant?: "primary" | "secondary" | "ghost" | "danger" | "success";
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
  min-height: 3rem;
  padding: 0 1rem;
  border: 1px solid transparent;
  border-radius: 1rem;
  font-size: var(--type-small);
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

.app-button :deep(svg) {
  width: 18px;
  height: 18px;
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
  box-shadow: 0 12px 28px rgba(37, 99, 255, 0.22);
}

.app-button--primary:hover:not(:disabled) {
  background: var(--color-primary-hover);
}

.app-button--secondary {
  background: rgba(255, 255, 255, 0.72);
  border-color: var(--color-border);
  color: var(--color-text);
}

.app-button--ghost {
  background: transparent;
  border-color: transparent;
  color: var(--color-text);
}

.app-button--danger {
  background: var(--color-danger-soft);
  border-color: transparent;
  color: var(--color-danger);
}

.app-button--success {
  background: var(--color-success-soft);
  border-color: transparent;
  color: var(--color-success);
}

.app-button--sm {
  min-height: 2.5rem;
  padding: 0 0.875rem;
}

.app-button--md {
  min-height: 3rem;
  padding: 0 1rem;
}

.app-button--lg {
  min-height: 3.5rem;
  padding: 0 1.25rem;
  font-size: var(--type-body);
}
</style>
