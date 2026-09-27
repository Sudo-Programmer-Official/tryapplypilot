<script setup lang="ts">
import { computed } from "vue";
import { RouterLink } from "vue-router";
import {
  BellRing,
  BriefcaseBusiness,
  CalendarCheck,
  Check,
  FileText,
  Mail,
  ShieldCheck,
  Target,
} from "lucide-vue-next";

import AppButton from "../../components/ui/AppButton.vue";
import { homeRouteForRole, useAuth } from "../../composables/useAuth";

const auth = useAuth();

const signedIn = computed(() => Boolean(auth.user.value));
const primaryRoute = computed(() => (auth.user.value ? homeRouteForRole(auth.user.value.role) : "/auth/signup"));
const primaryLabel = computed(() => (auth.user.value ? "Open your workspace" : "Get started"));
const year = new Date().getFullYear();

// Companies scanned by default; users can add or request more.
const companies = [
  "Anthropic",
  "Stripe",
  "Databricks",
  "Google",
  "NVIDIA",
  "Microsoft",
  "Figma",
  "Coinbase",
  "Cloudflare",
  "Notion",
  "Palantir",
  "Vercel",
];

const features = [
  {
    icon: Target,
    title: "Jobs matched to you",
    detail:
      "New roles are pulled straight from company career sites, scored against your resume and preferences, and explained: why it fits and what's missing.",
  },
  {
    icon: FileText,
    title: "Resume review you can trust",
    detail:
      "See how your resume stacks up for each job and get suggestions grounded in your real experience. You approve every change; nothing is invented.",
  },
  {
    icon: BriefcaseBusiness,
    title: "Every application, tracked",
    detail:
      "Click Apply and the job is tracked automatically. Record the submission, update the status and keep tasks, notes and deadlines in one place.",
  },
  {
    icon: Mail,
    title: "Recruiter inbox",
    detail:
      "Paste a recruiter email or connect Gmail read-only. Messages are linked to the right application, with reply drafts you review and send yourself.",
  },
  {
    icon: CalendarCheck,
    title: "Interview prep from your story",
    detail:
      "Get a preparation plan, likely questions and STAR stories built from your own projects and results, for each interview round.",
  },
  {
    icon: BellRing,
    title: "Alerts when it matters",
    detail:
      "Get the strongest matches on Telegram within minutes of posting, filtered by your minimum match score and notification window.",
  },
];

const steps = [
  { title: "Upload your resume", detail: "PDF, DOCX, TXT or Markdown. Your skills and experience are extracted automatically." },
  { title: "Pick companies and roles", detail: "Choose target companies, locations, seniority and how you like to work." },
  { title: "Review your matches", detail: "Open the roles that fit, tighten your resume for each one, and apply." },
  { title: "Track, reply and prepare", detail: "Follow each application from submission to offer, with recruiter context and interview prep." },
];

const principles = [
  "Never applies to jobs or sends emails on your behalf",
  "Resume suggestions come from your own experience, never invented",
  "Gmail access is read-only and optional",
  "Connected account tokens are encrypted at rest",
  "Delete a resume at any time",
];

const faqs = [
  {
    q: "Does TryApplyPilot apply to jobs for me?",
    a: "No. It finds and prepares; you decide. You apply on the company's own site, and when you click Apply the application is tracked for you.",
  },
  {
    q: "Which companies does it cover?",
    a: `It scans ${companies.slice(0, 6).join(", ")} and dozens of other tech companies directly from their career sites. You can choose which ones to follow and request companies that aren't covered yet.`,
  },
  {
    q: "Will it change or exaggerate my resume?",
    a: "Suggestions are grounded in evidence from your resume and profile, and each change needs your approval. Claims your experience doesn't support are flagged, not added.",
  },
  {
    q: "Do I need Gmail or Telegram?",
    a: "No, both are optional. You can paste recruiter emails by hand, and matches are always on your dashboard. Connect Gmail (read-only) or Telegram when you want them.",
  },
  {
    q: "What happens to my data?",
    a: "Your resumes, applications and messages belong to your account and are only used to power your own matches, prep and tracking. You can delete resumes whenever you like.",
  },
];
</script>

<template>
  <div class="landing">
    <a class="landing__skip" href="#main">Skip to content</a>

    <header class="landing__nav page-width">
      <RouterLink class="landing__brand" to="/" aria-label="TryApplyPilot home">
        <span class="landing__brand-mark" aria-hidden="true"></span>
        <span class="landing__brand-name">TryApplyPilot</span>
      </RouterLink>
      <nav class="landing__nav-links" aria-label="Primary">
        <a class="landing__link landing__link--section" href="#features">Features</a>
        <a class="landing__link landing__link--section" href="#how-it-works">How it works</a>
        <a class="landing__link landing__link--section" href="#faq">FAQ</a>
        <RouterLink v-if="!signedIn" class="landing__link" to="/auth/login">Log in</RouterLink>
        <AppButton size="sm" :href="primaryRoute">{{ primaryLabel }}</AppButton>
      </nav>
    </header>

    <main id="main">
      <section class="landing__hero page-width" aria-labelledby="hero-title">
        <div class="landing__hero-copy">
          <p class="landing__kicker">Your AI co-pilot for the job search</p>
          <h1 id="hero-title" class="landing__title">
            Find the right roles first. <span>Apply with confidence.</span>
          </h1>
          <p class="landing__lede">
            TryApplyPilot watches the companies you care about, matches new openings to your resume, and helps you
            tailor, track and prepare for every application, while you stay in control of what gets sent.
          </p>
          <div class="landing__actions">
            <AppButton size="lg" :href="primaryRoute">{{ primaryLabel }}</AppButton>
            <AppButton size="lg" variant="secondary" href="#how-it-works">See how it works</AppButton>
          </div>
          <ul class="landing__assurances list-reset">
            <li><Check aria-hidden="true" /> Set up in about five minutes</li>
            <li><Check aria-hidden="true" /> Never applies or emails without you</li>
          </ul>
        </div>

        <div class="landing__preview" role="img" aria-label="Example of a matched job card with a 94% match score">
          <p class="landing__preview-label">Example match</p>
          <article class="landing__match">
            <header class="landing__match-header">
              <span class="landing__match-logo" aria-hidden="true">S</span>
              <div>
                <p class="landing__match-company">Stripe · Seattle, WA</p>
                <h2 class="landing__match-title">Senior Software Engineer, Backend</h2>
              </div>
              <span class="landing__match-score"><strong>94%</strong> match</span>
            </header>
            <div class="landing__match-section">
              <p class="landing__match-heading">Why it fits</p>
              <div class="landing__chips">
                <span class="landing__chip landing__chip--good">Python</span>
                <span class="landing__chip landing__chip--good">Distributed systems</span>
                <span class="landing__chip landing__chip--good">Payments</span>
                <span class="landing__chip landing__chip--good">Senior</span>
              </div>
            </div>
            <div class="landing__match-section">
              <p class="landing__match-heading">Worth addressing</p>
              <div class="landing__chips">
                <span class="landing__chip landing__chip--gap">Kafka at scale</span>
              </div>
            </div>
            <footer class="landing__match-actions">
              <span class="landing__fake-button landing__fake-button--ghost">Review resume</span>
              <span class="landing__fake-button">Apply</span>
            </footer>
          </article>
          <div class="landing__toast" aria-hidden="true">
            <Check />
            <span><strong>Tracked in Applications</strong> Interview prep unlocks when you're scheduled.</span>
          </div>
        </div>
      </section>

      <section class="landing__companies page-width" aria-label="Companies covered">
        <p>Openings pulled directly from career sites at companies like</p>
        <ul class="list-reset">
          <li v-for="company in companies" :key="company">{{ company }}</li>
          <li class="landing__companies-more">and more</li>
        </ul>
      </section>

      <section id="features" class="landing__section page-width" aria-labelledby="features-title">
        <div class="landing__section-head">
          <p class="landing__kicker">Everything in one workspace</p>
          <h2 id="features-title" class="landing__section-title">From first match to final interview</h2>
          <p class="landing__section-lede">
            Stop juggling job boards, spreadsheets and inbox searches. Each step of the search builds on the last.
          </p>
        </div>
        <div class="landing__features">
          <article v-for="feature in features" :key="feature.title" class="landing__feature">
            <span class="landing__feature-icon" aria-hidden="true"><component :is="feature.icon" /></span>
            <h3>{{ feature.title }}</h3>
            <p>{{ feature.detail }}</p>
          </article>
        </div>
      </section>

      <section id="how-it-works" class="landing__section page-width" aria-labelledby="how-title">
        <div class="landing__section-head">
          <p class="landing__kicker">How it works</p>
          <h2 id="how-title" class="landing__section-title">Up and running in four steps</h2>
        </div>
        <ol class="landing__steps list-reset">
          <li v-for="(step, index) in steps" :key="step.title" class="landing__step">
            <span class="landing__step-number" aria-hidden="true">{{ index + 1 }}</span>
            <h3>{{ step.title }}</h3>
            <p>{{ step.detail }}</p>
          </li>
        </ol>
      </section>

      <section class="landing__section page-width" aria-labelledby="control-title">
        <div class="landing__control">
          <div class="landing__control-copy">
            <span class="landing__feature-icon" aria-hidden="true"><ShieldCheck /></span>
            <h2 id="control-title" class="landing__section-title">AI recommends. You decide.</h2>
            <p class="landing__section-lede">
              Your job search carries your name, so TryApplyPilot prepares and explains, and leaves every decision
              to you.
            </p>
          </div>
          <ul class="landing__principles list-reset">
            <li v-for="principle in principles" :key="principle"><Check aria-hidden="true" />{{ principle }}</li>
          </ul>
        </div>
      </section>

      <section id="faq" class="landing__section landing__section--narrow page-width" aria-labelledby="faq-title">
        <div class="landing__section-head">
          <p class="landing__kicker">FAQ</p>
          <h2 id="faq-title" class="landing__section-title">Questions, answered</h2>
        </div>
        <div class="landing__faq">
          <details v-for="faq in faqs" :key="faq.q" class="landing__faq-item">
            <summary>{{ faq.q }}</summary>
            <p>{{ faq.a }}</p>
          </details>
        </div>
      </section>

      <section class="landing__section page-width" aria-labelledby="cta-title">
        <div class="landing__cta">
          <h2 id="cta-title" class="landing__section-title">Make your next move with a co-pilot</h2>
          <p>Upload your resume, pick your companies, and see your first matches today.</p>
          <AppButton size="lg" :href="primaryRoute">{{ primaryLabel }}</AppButton>
        </div>
      </section>
    </main>

    <footer class="landing__footer page-width">
      <span class="landing__brand landing__brand--small">
        <span class="landing__brand-mark" aria-hidden="true"></span>
        TryApplyPilot
      </span>
      <nav class="landing__footer-links" aria-label="Footer">
        <a href="#features">Features</a>
        <a href="#faq">FAQ</a>
        <RouterLink to="/auth/login">Log in</RouterLink>
        <RouterLink to="/auth/signup">Create account</RouterLink>
      </nav>
      <span class="landing__copyright">© {{ year }} TryApplyPilot</span>
    </footer>
  </div>
</template>

<style scoped>
.landing {
  min-height: 100vh;
  background:
    radial-gradient(circle at 12% 0%, var(--color-primary-soft), transparent 34rem),
    radial-gradient(circle at 95% 18%, var(--color-info-soft), transparent 28rem),
    var(--color-background);
  scroll-behavior: smooth;
}

.landing__skip {
  position: absolute;
  left: var(--space-4);
  top: -4rem;
  z-index: 10;
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-sm);
  background: var(--color-primary-strong);
  color: white;
}

.landing__skip:focus {
  top: var(--space-4);
}

/* Navigation */
.landing__nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--content-gap);
  padding-block: var(--space-6);
}

.landing__brand {
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
  font-family: var(--font-display);
  font-size: 1.2rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.landing__brand--small {
  font-size: 1rem;
}

.landing__brand-mark {
  width: 1.6rem;
  height: 1.6rem;
  border-radius: 0.5rem;
  background:
    radial-gradient(circle, white 0 22%, transparent 24%),
    radial-gradient(circle, transparent 0 46%, white 48% 58%, transparent 60%),
    var(--color-primary);
}

.landing__nav-links {
  display: flex;
  align-items: center;
  gap: var(--space-6);
}

.landing__nav-links > * {
  white-space: nowrap;
}

.landing__link {
  color: var(--color-text-muted);
  font-weight: 500;
  transition: color var(--transition-fast);
}

.landing__link:hover {
  color: var(--color-text);
}

/* Hero */
.landing__hero {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
  gap: var(--space-12);
  align-items: center;
  padding-block: var(--space-12) var(--space-16);
}

.landing__hero-copy {
  display: grid;
  gap: var(--space-6);
}

.landing__kicker {
  margin: 0;
  color: var(--color-primary);
  font-size: var(--type-small);
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.landing__title {
  margin: 0;
  font-family: var(--font-display);
  font-size: clamp(2.5rem, 5.6vw, 4.25rem);
  line-height: 1.02;
  letter-spacing: -0.04em;
}

.landing__title span {
  display: block;
  color: var(--color-primary);
}

.landing__lede {
  margin: 0;
  max-width: 36rem;
  color: var(--color-text-muted);
  font-size: clamp(1.05rem, 1.6vw, 1.25rem);
  line-height: 1.6;
}

.landing__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.landing__assurances {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3) var(--space-6);
  color: var(--color-text-muted);
  font-size: var(--type-small);
}

.landing__assurances li,
.landing__principles li {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.landing__assurances svg,
.landing__principles svg {
  width: 1.1rem;
  height: 1.1rem;
  flex-shrink: 0;
  color: var(--color-success);
}

/* Hero preview */
.landing__preview {
  position: relative;
  display: grid;
  gap: var(--space-3);
  padding-bottom: 5.5rem;
}

.landing__preview-label {
  margin: 0;
  color: var(--color-text-muted);
  font-size: var(--type-caption);
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.landing__match {
  display: grid;
  gap: var(--space-5);
  padding: var(--space-6);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface-elevated);
  box-shadow: var(--shadow-lg);
}

.landing__match-header {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: var(--space-4);
  align-items: center;
}

.landing__match-logo {
  display: grid;
  place-items: center;
  width: 2.75rem;
  height: 2.75rem;
  border-radius: var(--radius-sm);
  background: var(--color-primary-soft);
  color: var(--color-primary-text);
  font-family: var(--font-display);
  font-weight: 700;
}

.landing__match-company,
.landing__match-heading {
  margin: 0;
  color: var(--color-text-muted);
  font-size: var(--type-small);
}

.landing__match-heading {
  margin-bottom: var(--space-2);
  font-weight: 600;
}

.landing__match-title {
  margin: var(--space-1) 0 0;
  font-family: var(--font-display);
  font-size: 1.15rem;
  line-height: 1.25;
}

.landing__match-score {
  display: grid;
  justify-items: center;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  background: var(--color-success-soft);
  color: var(--color-success-text);
  font-size: var(--type-caption);
  font-weight: 600;
}

.landing__match-score strong {
  font-family: var(--font-display);
  font-size: 1.4rem;
  line-height: 1.1;
}

.landing__chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.landing__chip {
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-pill);
  font-size: var(--type-small);
  font-weight: 500;
}

.landing__chip--good {
  background: var(--color-primary-soft);
  color: var(--color-primary-text);
}

.landing__chip--gap {
  background: var(--color-warning-soft);
  color: var(--color-text);
}

.landing__match-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
}

.landing__fake-button {
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-md);
  background: var(--color-primary-strong);
  color: white;
  font-size: var(--type-small);
  font-weight: 600;
}

.landing__fake-button--ghost {
  border: 1px solid var(--color-border-strong);
  background: transparent;
  color: var(--color-text);
}

.landing__toast {
  position: absolute;
  right: calc(-1 * var(--space-4));
  bottom: 0;
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  max-width: 20rem;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface-elevated);
  box-shadow: var(--shadow-md);
  color: var(--color-text-muted);
  font-size: var(--type-small);
  line-height: 1.45;
}

.landing__toast strong {
  display: block;
  color: var(--color-text);
}

.landing__toast svg {
  width: 1.25rem;
  height: 1.25rem;
  flex-shrink: 0;
  padding: 0.15rem;
  border-radius: 50%;
  background: var(--color-success-soft);
  color: var(--color-success);
}

/* Companies */
.landing__companies {
  display: grid;
  gap: var(--space-4);
  justify-items: center;
  padding-block: var(--space-8);
  border-block: 1px solid var(--color-border);
  text-align: center;
}

.landing__companies p {
  margin: 0;
  color: var(--color-text-muted);
  font-size: var(--type-small);
}

.landing__companies ul {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--space-3) var(--space-8);
  font-family: var(--font-display);
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--color-text);
  opacity: 0.8;
}

.landing__companies-more {
  color: var(--color-text-muted);
  font-family: var(--font-body);
  font-weight: 500;
}

/* Sections */
.landing__section {
  padding-block: var(--space-16) 0;
  scroll-margin-top: var(--space-4);
}

.landing__section--narrow {
  max-width: 52rem;
}

.landing__section-head {
  display: grid;
  gap: var(--space-3);
  max-width: 40rem;
  margin-bottom: var(--space-10);
}

.landing__section-title {
  margin: 0;
  font-family: var(--font-display);
  font-size: clamp(1.9rem, 3.4vw, 2.75rem);
  line-height: 1.1;
  letter-spacing: -0.03em;
}

.landing__section-lede {
  margin: 0;
  color: var(--color-text-muted);
  font-size: 1.1rem;
  line-height: 1.6;
}

.landing__features {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-6);
}

.landing__feature,
.landing__step {
  display: grid;
  align-content: start;
  gap: var(--space-3);
  padding: var(--space-6);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
}

.landing__feature h3,
.landing__step h3 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.2rem;
}

.landing__feature p,
.landing__step p {
  margin: 0;
  color: var(--color-text-muted);
  line-height: 1.6;
}

.landing__feature-icon {
  display: grid;
  place-items: center;
  width: 2.75rem;
  height: 2.75rem;
  border-radius: var(--radius-md);
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.landing__feature-icon svg {
  width: 1.35rem;
  height: 1.35rem;
}

.landing__steps {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 14rem), 1fr));
  gap: var(--space-6);
}

.landing__step-number {
  display: grid;
  place-items: center;
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 50%;
  background: var(--color-primary-strong);
  color: white;
  font-family: var(--font-display);
  font-weight: 700;
}

/* Control */
.landing__control {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: var(--space-10);
  align-items: center;
  padding: var(--space-10);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  background: var(--color-surface);
}

.landing__control-copy {
  display: grid;
  gap: var(--space-4);
}

.landing__principles {
  display: grid;
  gap: var(--space-4);
  font-weight: 500;
}

/* FAQ */
.landing__faq {
  display: grid;
  gap: var(--space-3);
}

.landing__faq-item {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
}

.landing__faq-item summary {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-5) var(--space-6);
  font-weight: 600;
  cursor: pointer;
  list-style: none;
}

.landing__faq-item summary::-webkit-details-marker {
  display: none;
}

.landing__faq-item summary::after {
  content: "+";
  color: var(--color-primary);
  font-size: 1.25rem;
  line-height: 1;
}

.landing__faq-item[open] summary::after {
  content: "−";
}

.landing__faq-item p {
  margin: 0;
  padding: 0 var(--space-6) var(--space-5);
  color: var(--color-text-muted);
  line-height: 1.65;
}

/* Final CTA */
.landing__cta {
  display: grid;
  justify-items: center;
  gap: var(--space-4);
  padding: var(--space-12) var(--space-6);
  border-radius: var(--radius-xl);
  /* Fixed deep blue in both themes so white text keeps AA contrast. */
  background:
    radial-gradient(circle at 20% 0%, rgba(255, 255, 255, 0.16), transparent 22rem),
    linear-gradient(135deg, #1740c8 0%, #2563ff 100%);
  color: white;
  text-align: center;
}

.landing__cta p {
  margin: 0 0 var(--space-2);
  max-width: 32rem;
  color: rgba(255, 255, 255, 0.92);
  font-size: 1.1rem;
}

.landing__cta :deep(.app-button) {
  background: white;
  color: #1740c8;
  box-shadow: none;
}

/* Footer */
.landing__footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  margin-top: var(--space-16);
  padding-block: var(--space-8);
  border-top: 1px solid var(--color-border);
  color: var(--color-text-muted);
  font-size: var(--type-small);
}

.landing__footer-links {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-6);
}

.landing__footer-links a:hover {
  color: var(--color-text);
}

@media (max-width: 1023px) {
  .landing__features {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .landing__hero {
    grid-template-columns: 1fr;
    gap: var(--space-10);
    padding-block: var(--space-8) var(--space-12);
  }

  .landing__preview {
    max-width: 34rem;
  }

  .landing__toast {
    right: 0;
  }

  .landing__control {
    grid-template-columns: 1fr;
    gap: var(--space-8);
    padding: var(--space-8);
  }
}

@media (max-width: 767px) {
  .landing__features {
    grid-template-columns: 1fr;
  }

  .landing__link--section {
    display: none;
  }

  .landing__nav-links {
    gap: var(--space-3);
  }

  .landing__nav > .landing__brand {
    gap: var(--space-2);
    font-size: 1.02rem;
  }

  .landing__nav .landing__brand-mark {
    width: 1.35rem;
    height: 1.35rem;
  }

  .landing__section {
    padding-top: var(--space-12);
  }

  .landing__control {
    padding: var(--space-6);
  }

  .landing__match {
    padding: var(--space-5);
  }

  .landing__match-header {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .landing__match-score {
    grid-column: 1 / -1;
    grid-auto-flow: column;
    justify-content: start;
    align-items: baseline;
    gap: var(--space-2);
  }

  .landing__toast {
    position: static;
    max-width: none;
  }

  .landing__preview {
    padding-bottom: 0;
  }
}

@media (max-width: 359px) {
  .landing__nav .landing__brand-name {
    display: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .landing {
    scroll-behavior: auto;
  }
}
</style>
