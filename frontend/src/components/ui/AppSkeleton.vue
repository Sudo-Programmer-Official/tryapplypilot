<template>
  <span class="app-skeleton" />
</template>

<style scoped>
.app-skeleton {
  display: block;
  width: 100%;
  min-height: 1rem;
  border-radius: var(--radius-sm);
  background: linear-gradient(90deg, var(--color-surface-muted) 0%, rgba(255, 255, 255, 0.75) 50%, var(--color-surface-muted) 100%);
  background-size: 200% 100%;
  animation: shimmer 1.2s infinite linear;
}

@keyframes shimmer {
  from {
    background-position: 200% 0;
  }

  to {
    background-position: -200% 0;
  }
}
</style>
