<script setup lang="ts">
import AppBadge from "./AppBadge.vue";
import { useToast } from "../../composables/useToast";

const { toasts, dismissToast } = useToast();
</script>

<template>
  <Teleport to="body">
    <div class="app-toast-stack" aria-live="polite" aria-atomic="true">
      <article v-for="toast in toasts" :key="toast.id" class="app-toast surface-panel">
        <div class="app-toast__header">
          <AppBadge :tone="toast.tone === 'success' ? 'success' : toast.tone === 'error' ? 'danger' : 'info'" size="sm">
            {{ toast.tone }}
          </AppBadge>
          <button class="app-toast__close" :aria-label="`Dismiss ${toast.title}`" @click="dismissToast(toast.id)">×</button>
        </div>
        <strong>{{ toast.title }}</strong>
        <p v-if="toast.description">{{ toast.description }}</p>
      </article>
    </div>
  </Teleport>
</template>

<style scoped>
.app-toast-stack {
  position: fixed;
  right: var(--space-4);
  bottom: var(--space-4);
  z-index: 90;
  display: grid;
  gap: var(--space-3);
  width: min(22rem, calc(100vw - 2rem));
}

.app-toast {
  padding: var(--space-4);
}

.app-toast__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-2);
}

.app-toast p {
  margin: var(--space-2) 0 0;
  color: var(--color-text-muted);
  font-size: 0.9rem;
}

.app-toast__close {
  border: 0;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
}
</style>
