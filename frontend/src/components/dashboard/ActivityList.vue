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
      <div class="activity-list__copy">
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
  gap: var(--space-4);
}

.activity-list__item {
  position: relative;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: var(--space-4);
  align-items: center;
  padding: var(--space-5) var(--space-5) var(--space-5) var(--space-6);
  border: 1px solid rgba(15, 29, 58, 0.08);
  border-radius: var(--radius-lg);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(246, 249, 253, 0.98));
  box-shadow: 0 14px 28px rgba(15, 29, 58, 0.05);
  transition:
    transform var(--transition-base),
    box-shadow var(--transition-base),
    border-color var(--transition-base);
}

.activity-list__item:hover {
  transform: translateY(-2px);
  box-shadow: 0 20px 38px rgba(15, 29, 58, 0.08);
  border-color: rgba(37, 99, 255, 0.12);
}

.activity-list__dot {
  width: 1rem;
  height: 1rem;
  border-radius: 50%;
  box-shadow: 0 0 0 8px rgba(255, 255, 255, 0.84);
}

.activity-list__copy {
  min-width: 0;
}

.activity-list__copy strong {
  display: block;
  font-size: clamp(1rem, 1.4vw, 1.1rem);
  line-height: 1.35;
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
  margin: var(--space-2) 0 0;
  color: var(--color-text-muted);
  font-size: 0.95rem;
  line-height: 1.55;
}

.activity-list__age {
  align-self: start;
  padding-top: var(--space-1);
  white-space: nowrap;
}

@media (max-width: 767px) {
  .activity-list__item {
    grid-template-columns: auto minmax(0, 1fr);
    padding: var(--space-4) var(--space-4) var(--space-4) var(--space-5);
  }

  .activity-list__age {
    grid-column: 2;
    margin-top: var(--space-1);
    padding-top: 0;
  }
}
</style>
