<script setup lang="ts">
withDefaults(
  defineProps<{
    tone?: "neutral" | "primary" | "success" | "warning" | "danger" | "info";
    size?: "sm" | "md";
  }>(),
  {
    tone: "neutral",
    size: "md",
  },
);
</script>

<template>
  <span class="app-badge" :class="[`app-badge--${tone}`, `app-badge--${size}`]">
    <slot />
  </span>
</template>

<style scoped>
.app-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  border-radius: var(--radius-pill);
  font-weight: 600;
  white-space: nowrap;
}

.app-badge--sm {
  padding: 0.25rem 0.55rem;
  font-size: 0.72rem;
}

.app-badge--md {
  padding: 0.35rem 0.7rem;
  font-size: 0.78rem;
}

.app-badge--neutral {
  background: var(--color-surface-muted);
  color: var(--color-text-muted);
}

.app-badge--primary {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.app-badge--success {
  background: var(--color-success-soft);
  color: var(--color-success);
}

.app-badge--warning {
  background: var(--color-warning-soft);
  color: var(--color-warning);
}

.app-badge--danger {
  background: var(--color-danger-soft);
  color: var(--color-danger);
}

.app-badge--info {
  background: var(--color-info-soft);
  color: var(--color-info);
}
</style>
