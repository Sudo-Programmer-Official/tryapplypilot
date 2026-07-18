<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps<{
  open: boolean;
  title: string;
  description?: string;
}>();

const emit = defineEmits<{
  (event: "close"): void;
}>();

const panel = ref<HTMLElement | null>(null);

function trapFocus(event: KeyboardEvent): void {
  if (!props.open || event.key !== "Tab" || !panel.value) {
    return;
  }
  const nodes = panel.value.querySelectorAll<HTMLElement>(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
  );
  const focusable = Array.from(nodes).filter((node) => !node.hasAttribute("disabled"));
  if (focusable.length === 0) {
    return;
  }
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  const current = document.activeElement;
  if (event.shiftKey && current === first) {
    last.focus();
    event.preventDefault();
  } else if (!event.shiftKey && current === last) {
    first.focus();
    event.preventDefault();
  }
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape" && props.open) {
    emit("close");
  }
  trapFocus(event);
}

watch(
  () => props.open,
  (open) => {
    document.body.style.overflow = open ? "hidden" : "";
    if (open) {
      window.setTimeout(() => panel.value?.focus(), 0);
    }
  },
);

onMounted(() => window.addEventListener("keydown", onKeydown));
onBeforeUnmount(() => {
  document.body.style.overflow = "";
  window.removeEventListener("keydown", onKeydown);
});

const describedBy = computed(() => `${props.title.replace(/\s+/g, "-").toLowerCase()}-description`);
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="app-modal">
      <button class="app-modal__backdrop" aria-label="Close dialog" @click="$emit('close')" />
      <section ref="panel" class="app-modal__panel surface-panel" role="dialog" aria-modal="true" :aria-labelledby="title" :aria-describedby="describedBy" tabindex="-1">
        <header class="app-modal__header">
          <div>
            <h2 class="app-modal__title">{{ title }}</h2>
            <p v-if="description" :id="describedBy" class="app-modal__copy">{{ description }}</p>
          </div>
        </header>
        <div class="app-modal__body">
          <slot />
        </div>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.app-modal {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: grid;
  place-items: center;
  padding: var(--space-4);
}

.app-modal__backdrop {
  position: absolute;
  inset: 0;
  border: 0;
  background: rgba(7, 17, 34, 0.58);
}

.app-modal__panel {
  position: relative;
  width: min(100%, 40rem);
  padding: var(--space-6);
}

.app-modal__header {
  margin-bottom: var(--space-5);
}

.app-modal__title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.4rem;
}

.app-modal__copy {
  margin: var(--space-2) 0 0;
  color: var(--color-text-muted);
}
</style>
