<script setup lang="ts">
import { computed } from "vue";
import { RouterLink } from "vue-router";

import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
import AppSection from "../../components/layout/AppSection.vue";
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

    <AppPage as="main" class="landing__main">
      <section class="landing__hero">
        <div class="landing__copy">
          <AppBadge tone="primary">AI Job Radar</AppBadge>
          <h1 class="type-display-xl">Never miss a job you&rsquo;re qualified for.</h1>
          <p class="type-body-lg">
            TryApplyPilot watches target companies, scores each new role against your profile, and sends the high-match
            openings to you before the queue gets crowded.
          </p>
          <div class="landing__actions">
            <AppButton size="lg" :href="primaryRoute">{{ primaryLabel }}</AppButton>
            <AppButton size="lg" variant="secondary" href="/auth/login">See the user dashboard</AppButton>
          </div>
          <ul class="landing__list list-reset">
            <li v-for="step in steps" :key="step">{{ step }}</li>
          </ul>
        </div>

        <AppCard class="landing__signal">
          <template #header>
            <div>
              <p class="eyebrow">Live signal</p>
              <h2 class="type-heading">What the product does every few minutes</h2>
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
              <strong class="type-title">5 min</strong>
            </div>
            <div>
              <span class="eyebrow">Channels</span>
              <strong class="type-title">Telegram first</strong>
            </div>
            <div>
              <span class="eyebrow">Scope</span>
              <strong class="type-title">User-specific alerts</strong>
            </div>
          </div>
        </AppCard>
      </section>

      <AppSection eyebrow="How it works" title="Built for the job seeker first">
        <AppGrid class="landing__grid" columns="3">
          <AppCard v-for="highlight in highlights" :key="highlight.title" :title="highlight.title" :subtitle="highlight.detail" />
        </AppGrid>
      </AppSection>
    </AppPage>

    <footer class="landing__footer page-width">
      <span class="type-caption">Job discovery, scoring, and notifications focused on the user workflow.</span>
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
  gap: var(--content-gap);
  padding-top: var(--page-padding-y);
  padding-bottom: var(--page-padding-y);
}

.landing__brand {
  font-family: var(--font-display);
  font-size: var(--type-title);
  font-weight: 700;
}

.landing__nav-links,
.landing__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--content-gap);
}

.landing__link {
  color: var(--color-text-muted);
}

.landing__main {
  align-content: center;
}

.landing__hero {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(320px, 0.9fr);
  gap: calc(var(--section-gap) + var(--content-gap));
  align-items: center;
  min-height: min(72vh, 52rem);
}

.landing__copy {
  display: grid;
  gap: var(--content-gap);
  max-width: var(--hero-copy-max-width);
}

.landing__copy p {
  color: var(--color-text-muted);
}

.landing__list {
  display: grid;
  gap: var(--content-gap);
  margin-top: var(--content-gap);
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
  gap: var(--card-gap);
  max-width: var(--hero-card-max-width);
  justify-self: end;
}

.landing__signal-flow {
  display: grid;
  gap: var(--content-gap);
}

.landing__signal-flow span {
  padding: var(--content-gap) var(--card-padding);
  border-radius: var(--radius-lg);
  background: var(--color-surface-muted);
}

.landing__alert {
  padding: var(--card-padding);
}

.landing__alert-title {
  margin: 0 0 var(--space-2);
  color: var(--color-danger);
  font-weight: 700;
}

.landing__stats,
.landing__grid {
  display: grid;
  gap: var(--content-gap);
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}

.landing__stats :deep(strong) {
  display: block;
  margin-top: var(--space-2);
}

.landing__footer {
  padding-top: 0;
  color: var(--color-text-muted);
}

@media (max-width: 1023px) {
  .landing__hero {
    grid-template-columns: 1fr;
    min-height: auto;
  }

  .landing__signal {
    justify-self: stretch;
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
