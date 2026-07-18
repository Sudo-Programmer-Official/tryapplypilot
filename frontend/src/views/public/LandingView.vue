<script setup lang="ts">
import { computed } from "vue";
import { RouterLink } from "vue-router";

import AppBadge from "../../components/ui/AppBadge.vue";
import AppButton from "../../components/ui/AppButton.vue";
import AppCard from "../../components/ui/AppCard.vue";
import { homeRouteForRole, useAuth } from "../../composables/useAuth";

const auth = useAuth();

const primaryRoute = computed(() => (auth.user.value ? homeRouteForRole(auth.user.value.role) : "/auth/signup"));
const primaryLabel = computed(() => (auth.user.value ? "Open Workspace" : "Create Account"));

const steps = [
  "Create an account",
  "Upload your resume",
  "Choose companies and locations",
  "Connect Telegram",
  "Get instant job alerts",
];

const highlights = [
  { title: "Fresh roles in minutes", detail: "The scout checks live connectors on a five-minute cadence and only surfaces newly posted jobs." },
  { title: "Resume-aware matching", detail: "Each job is scored against your profile so the feed stays focused on roles worth opening." },
  { title: "Private delivery", detail: "Telegram notifications go straight to your bot chat instead of a noisy group or shared inbox." },
];
</script>

<template>
  <div class="landing">
    <header class="landing__nav page-width">
      <RouterLink class="landing__brand" to="/">TryApplyPilot</RouterLink>
      <div class="landing__nav-links">
        <RouterLink class="landing__link" to="/auth/login">Login</RouterLink>
        <RouterLink class="landing__link" to="/auth/signup">Create account</RouterLink>
      </div>
    </header>

    <main class="page-width landing__main">
      <section class="landing__hero">
        <div class="landing__copy">
          <AppBadge tone="primary">AI Job Radar</AppBadge>
          <h1>Never miss a job you&rsquo;re qualified for.</h1>
          <p>
            TryApplyPilot watches target companies, scores each new role against your profile, and sends the high-match
            openings to you before the queue gets crowded.
          </p>
          <div class="landing__actions">
            <RouterLink :to="primaryRoute" class="landing__button landing__button--primary">{{ primaryLabel }}</RouterLink>
            <RouterLink to="/auth/login" class="landing__button landing__button--secondary">See the user dashboard</RouterLink>
          </div>
          <ul class="landing__list list-reset">
            <li v-for="step in steps" :key="step">{{ step }}</li>
          </ul>
        </div>

        <AppCard class="landing__signal">
          <template #header>
            <div>
              <p class="eyebrow">Live signal</p>
              <h2>What the product does every few minutes</h2>
            </div>
          </template>

          <div class="landing__signal-flow">
            <span>Collect jobs</span>
            <span>Normalize</span>
            <span>Deduplicate</span>
            <span>Match score</span>
            <span>Notify</span>
          </div>

          <div class="landing__alert surface-panel">
            <p class="landing__alert-title">New High-Match Job</p>
            <strong>Databricks · Senior Software Engineer</strong>
            <p>Posted 4 min ago · 94% match · Backend AI resume</p>
          </div>

          <div class="landing__stats">
            <div>
              <span class="eyebrow">Cadence</span>
              <strong>5 min</strong>
            </div>
            <div>
              <span class="eyebrow">Channels</span>
              <strong>Telegram first</strong>
            </div>
            <div>
              <span class="eyebrow">Scope</span>
              <strong>User-specific alerts</strong>
            </div>
          </div>
        </AppCard>
      </section>

      <section class="landing__section">
        <div class="landing__section-header">
          <p class="eyebrow">How it works</p>
          <h2>Built for the job seeker first</h2>
        </div>
        <div class="landing__grid">
          <AppCard v-for="highlight in highlights" :key="highlight.title" :title="highlight.title" :subtitle="highlight.detail" />
        </div>
      </section>
    </main>

    <footer class="landing__footer page-width">
      <span>Job discovery, scoring, and notifications focused on the user workflow.</span>
    </footer>
  </div>
</template>

<style scoped>
.landing {
  min-height: 100vh;
  background:
    radial-gradient(circle at top left, rgba(35, 98, 255, 0.16), transparent 28rem),
    radial-gradient(circle at bottom right, rgba(15, 163, 177, 0.12), transparent 32rem),
    var(--color-background);
}

.landing__nav,
.landing__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding-top: var(--space-5);
  padding-bottom: var(--space-5);
}

.landing__brand {
  font-family: var(--font-display);
  font-size: 1.15rem;
  font-weight: 700;
}

.landing__nav-links,
.landing__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.landing__link {
  color: var(--color-text-muted);
}

.landing__main {
  display: grid;
  gap: var(--space-8);
  padding-bottom: var(--space-8);
}

.landing__hero {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(320px, 0.9fr);
  gap: var(--space-6);
  align-items: center;
  padding: var(--space-8) 0 var(--space-4);
}

.landing__copy h1 {
  margin: var(--space-4) 0 var(--space-3);
  font-family: var(--font-display);
  font-size: clamp(2.8rem, 6vw, 4.7rem);
  line-height: 0.96;
  letter-spacing: -0.05em;
}

.landing__copy p {
  max-width: 42rem;
  color: var(--color-text-muted);
  font-size: 1.02rem;
}

.landing__button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 46px;
  padding: 0 var(--space-5);
  border-radius: var(--radius-pill);
  font-weight: 700;
}

.landing__button--primary {
  background: var(--color-primary);
  color: white;
}

.landing__button--secondary {
  border: 1px solid var(--color-border);
  background: var(--color-surface-elevated);
}

.landing__list {
  display: grid;
  gap: var(--space-3);
  margin-top: var(--space-5);
}

.landing__list li {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  color: var(--color-text);
}

.landing__list li::before {
  content: "";
  width: 0.7rem;
  height: 0.7rem;
  border-radius: 50%;
  background: var(--color-success);
}

.landing__signal {
  gap: var(--space-5);
  padding: var(--space-6);
}

.landing__signal h2 {
  margin: var(--space-2) 0 0;
  font-family: var(--font-display);
  font-size: 1.8rem;
}

.landing__signal-flow {
  display: grid;
  gap: var(--space-3);
}

.landing__signal-flow span {
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-lg);
  background: var(--color-surface-muted);
}

.landing__alert {
  padding: var(--space-5);
}

.landing__alert-title {
  margin: 0 0 var(--space-2);
  color: var(--color-danger);
  font-weight: 700;
}

.landing__stats,
.landing__grid {
  display: grid;
  gap: var(--space-4);
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}

.landing__stats strong {
  display: block;
  margin-top: var(--space-2);
  font-family: var(--font-display);
  font-size: 1.2rem;
}

.landing__section {
  display: grid;
  gap: var(--space-5);
}

.landing__section-header h2 {
  margin: var(--space-2) 0 0;
  font-family: var(--font-display);
  font-size: 2rem;
}

.landing__footer {
  padding-top: 0;
  color: var(--color-text-muted);
  font-size: 0.92rem;
}

@media (max-width: 1023px) {
  .landing__hero {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 767px) {
  .landing__nav,
  .landing__footer {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
