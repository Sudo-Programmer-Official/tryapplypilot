<script setup lang="ts">
defineProps<{
  text: string;
  disabled?: boolean;
}>();
</script>

<template>
  <div class="app-tooltip" :class="{ 'app-tooltip--disabled': disabled }">
    <slot />
    <span class="app-tooltip__bubble" role="tooltip">{{ text }}</span>
  </div>
</template>

<style scoped>
.app-tooltip {
  position: relative;
}

.app-tooltip--disabled .app-tooltip__bubble {
  display: none;
}

.app-tooltip__bubble {
  position: absolute;
  left: calc(100% + var(--space-2));
  top: 50%;
  transform: translateY(-50%);
  padding: 0.45rem 0.65rem;
  border-radius: var(--radius-sm);
  background: rgba(7, 17, 34, 0.92);
  color: white;
  font-size: 0.74rem;
  opacity: 0;
  pointer-events: none;
  transition: opacity var(--transition-fast);
  white-space: nowrap;
  z-index: 5;
}

.app-tooltip:hover .app-tooltip__bubble,
.app-tooltip:focus-within .app-tooltip__bubble {
  opacity: 1;
}
</style>
