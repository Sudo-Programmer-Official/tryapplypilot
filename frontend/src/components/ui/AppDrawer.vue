<script setup lang="ts">
import { onBeforeUnmount, onMounted, watch } from "vue";

const props = withDefaults(
  defineProps<{
    open: boolean;
    title?: string;
    description?: string;
    side?: "left" | "right";
    width?: "sm" | "md" | "lg";
  }>(),
  {
    title: "",
    description: "",
    side: "left",
    width: "md",
  },
);

const emit = defineEmits<{
  (event: "close"): void;
}>();

function onKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape" && props.open) {
    emit("close");
  }
}

watch(
  () => props.open,
  (open) => {
    document.body.style.overflow = open ? "hidden" : "";
  },
);

onMounted(() => window.addEventListener("keydown", onKeydown));
onBeforeUnmount(() => {
  document.body.style.overflow = "";
  window.removeEventListener("keydown", onKeydown);
});
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="app-drawer">
      <button class="app-drawer__backdrop" aria-label="Close menu" @click="$emit('close')" />
      <aside class="app-drawer__panel" :class="[`app-drawer__panel--${props.side}`, `app-drawer__panel--${props.width}`]">
        <header v-if="props.title || props.description || $slots.header" class="app-drawer__header">
          <slot name="header">
            <div>
              <h2 v-if="props.title" class="app-drawer__title">{{ props.title }}</h2>
              <p v-if="props.description" class="app-drawer__description">{{ props.description }}</p>
            </div>
          </slot>
          <button class="app-drawer__close" aria-label="Close drawer" @click="$emit('close')">×</button>
        </header>
        <div class="app-drawer__body">
          <slot />
        </div>
      </aside>
    </div>
  </Teleport>
</template>

<style scoped>
.app-drawer {
  position: fixed;
  inset: 0;
  z-index: 70;
}

.app-drawer__backdrop {
  position: absolute;
  inset: 0;
  border: 0;
  background: rgba(7, 17, 34, 0.58);
  animation: drawer-fade var(--transition-base);
}

.app-drawer__panel {
  position: absolute;
  top: 0;
  bottom: 0;
  width: min(92vw, 30rem);
  height: 100%;
  background: var(--color-surface-elevated);
  animation: drawer-slide var(--transition-slow);
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
}

.app-drawer__panel--left {
  left: 0;
  border-right: 1px solid var(--color-border);
  animation-name: drawer-slide-left;
}

.app-drawer__panel--right {
  right: 0;
  border-left: 1px solid var(--color-border);
  animation-name: drawer-slide-right;
}

.app-drawer__panel--sm {
  width: min(92vw, 24rem);
}

.app-drawer__panel--md {
  width: min(92vw, 30rem);
}

.app-drawer__panel--lg {
  width: min(92vw, 38rem);
}

.app-drawer__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-5);
  border-bottom: 1px solid var(--color-border);
}

.app-drawer__title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.25rem;
}

.app-drawer__description {
  margin: var(--space-2) 0 0;
  color: var(--color-text-muted);
  font-size: 0.9rem;
}

.app-drawer__close {
  width: 2.5rem;
  height: 2.5rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface-muted);
  color: var(--color-text);
  cursor: pointer;
}

.app-drawer__body {
  min-height: 0;
  overflow-y: auto;
}

@keyframes drawer-fade {
  from {
    opacity: 0;
  }

  to {
    opacity: 1;
  }
}

@keyframes drawer-slide-left {
  from {
    transform: translateX(-24px);
    opacity: 0;
  }

  to {
    transform: translateX(0);
    opacity: 1;
  }
}

@keyframes drawer-slide-right {
  from {
    transform: translateX(24px);
    opacity: 0;
  }

  to {
    transform: translateX(0);
    opacity: 1;
  }
}
</style>
