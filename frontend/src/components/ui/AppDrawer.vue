<script setup lang="ts">
import { onBeforeUnmount, onMounted, watch } from "vue";

const props = defineProps<{
  open: boolean;
  title: string;
}>();

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
      <aside class="app-drawer__panel">
        <slot />
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
}

.app-drawer__panel {
  position: relative;
  width: min(88vw, 21rem);
  height: 100%;
}
</style>
