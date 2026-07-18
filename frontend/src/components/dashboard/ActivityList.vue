<script setup lang="ts">
defineProps<{
  items: Array<{
    id: string;
    title: string;
    detail: string;
    age: string;
    tone?: "success" | "warning" | "danger" | "info";
  }>;
}>();
</script>

<template>
  <ul class="activity-list list-reset">
    <li v-for="item in items" :key="item.id" class="activity-list__item">
      <span class="activity-list__dot" :class="`activity-list__dot--${item.tone ?? 'info'}`" />
      <div>
        <strong>{{ item.title }}</strong>
        <p>{{ item.detail }}</p>
      </div>
      <span class="activity-list__age">{{ item.age }}</span>
    </li>
  </ul>
</template>

<style scoped>
.activity-list {
  display: grid;
  gap: var(--content-gap);
}

.activity-list__item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: var(--content-gap);
  align-items: start;
}

.activity-list__dot {
  width: 0.85rem;
  height: 0.85rem;
  border-radius: 50%;
  margin-top: 0.35rem;
}

.activity-list__dot--success {
  background: var(--color-success);
}

.activity-list__dot--warning {
  background: var(--color-warning);
}

.activity-list__dot--danger {
  background: var(--color-danger);
}

.activity-list__dot--info {
  background: var(--color-info);
}

.activity-list__item p,
.activity-list__age {
  margin: var(--space-1) 0 0;
  color: var(--color-text-muted);
  font-size: var(--type-small);
}
</style>
