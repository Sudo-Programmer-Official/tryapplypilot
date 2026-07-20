<script setup lang="ts">
import { computed, ref } from "vue";
import { RouterLink, useRouter } from "vue-router";

import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
import PageSection from "../../components/layout/PageSection.vue";
import AppBadge from "../../components/ui/AppBadge.vue";
import AppButton from "../../components/ui/AppButton.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppInput from "../../components/ui/AppInput.vue";
import { homeRouteForRole, useAuth } from "../../composables/useAuth";
import { useToast } from "../../composables/useToast";

const props = defineProps<{
  mode: "login" | "signup" | "forgot";
  audience: "user" | "admin";
}>();

const router = useRouter();
const auth = useAuth();
const { pushToast } = useToast();

const fullName = ref("");
const email = ref("");
const password = ref("");
const submitting = ref(false);
const error = ref<string | null>(null);
const resetNotice = ref<string | null>(null);

const isLogin = computed(() => props.mode === "login");
const isSignup = computed(() => props.mode === "signup");
const isForgot = computed(() => props.mode === "forgot");
const isAdmin = computed(() => props.audience === "admin");

const heading = computed(() => {
  if (isForgot.value) {
    return "Reset your password";
  }
  if (isSignup.value) {
    return "Create your account";
  }
  return isAdmin.value ? "Admin login" : "Welcome back";
});

const description = computed(() => {
  if (isForgot.value) {
    return "The UI is ready, but the reset endpoint has not been wired yet.";
  }
  return isAdmin.value
    ? "Operations access stays separate from the default user flow."
    : "Sign in to manage your job radar, preferences, resumes, and alerts.";
});

const cardTitle = computed(() => {
  if (isForgot.value) {
    return "Reset request";
  }
  if (isSignup.value) {
    return "Create your workspace";
  }
  return isAdmin.value ? "Admin access" : "Sign in";
});

const cardSubtitle = computed(() => {
  if (isForgot.value) {
    return "Enter your email and we will route the request once the backend reset flow is connected.";
  }
  if (isSignup.value) {
    return "Use one account for job tracking, resumes, preferences, and private alerts.";
  }
  return isAdmin.value
    ? "Use your operations credentials to reach the admin console."
    : "Use your account email and password to return to the user workspace.";
});

const authNotes = computed(() => {
  if (isAdmin.value) {
    return [
      {
        title: "Separate routing",
        detail: "Admin sessions stay under /admin/* with role-gated navigation and workspace separation.",
      },
      {
        title: "Shared account model",
        detail: "Profiles, resumes, alerts, and company preferences stay tied to the same underlying account record.",
      },
      {
        title: "Operational visibility",
        detail: "Connector health, logs, requests, notifications, and settings remain available from one console.",
      },
    ];
  }

  return [
    {
      title: "Direct workspace landing",
      detail: "User login always lands on the job-seeker dashboard with your latest jobs, alerts, and onboarding status.",
    },
    {
      title: "One profile across features",
      detail: "Telegram, resumes, preferences, saved jobs, and company targeting all stay on one account model.",
    },
    {
      title: "Tighter job triage",
      detail: "Your workspace keeps matching thresholds, freshness windows, and watchlists aligned with your search.",
    },
  ];
});

const submitLabel = computed(() => {
  if (isForgot.value) {
    return "Request reset";
  }
  return isSignup.value ? "Create account" : "Login";
});

async function handleSubmit(): Promise<void> {
  error.value = null;
  resetNotice.value = null;
  submitting.value = true;
  try {
    if (isForgot.value) {
      resetNotice.value = "Password reset still needs a backend endpoint. Use admin support for now.";
      pushToast("Reset flow not connected", "The form is ready, but there is no backend reset endpoint yet.", "info");
      return;
    }

    const user = isSignup.value
      ? await auth.signupWithPassword(email.value, password.value, fullName.value)
      : await auth.loginWithPassword(email.value, password.value);

    pushToast(isSignup.value ? "Account created" : "Login successful", "Routing to your workspace.", "success");
    await router.push(homeRouteForRole(user.role));
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Authentication failed.";
    pushToast("Authentication failed", error.value, "error");
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <div class="auth">
    <AppPage class="auth__page" centered>
      <PageSection>
        <AppGrid class="auth__panel" columns="2">
          <section class="auth__intro" aria-label="Authentication overview">
            <div class="auth__hero">
              <RouterLink class="auth__brand" to="/">TryApplyPilot</RouterLink>
              <AppBadge :tone="isAdmin ? 'warning' : 'primary'">
                {{ isAdmin ? "Admin Portal" : "User Portal" }}
              </AppBadge>
              <div class="auth__headline">
                <h1 class="type-display">{{ heading }}</h1>
                <p class="type-body-lg">{{ description }}</p>
              </div>
            </div>

            <ul class="auth__notes list-reset">
              <li v-for="note in authNotes" :key="note.title">
                <strong>{{ note.title }}</strong>
                <p>{{ note.detail }}</p>
              </li>
            </ul>
          </section>

          <AppCard class="auth__card" :title="cardTitle" :subtitle="cardSubtitle">
            <form class="app-form-grid auth__form" @submit.prevent="handleSubmit">
              <AppInput
                v-if="isSignup"
                v-model="fullName"
                autocomplete="name"
                label="Full name"
                name="fullName"
                placeholder="Abhishek Kumar Jha"
                required
              />
              <AppInput
                v-model="email"
                autocomplete="email"
                label="Email"
                name="email"
                placeholder="you@example.com"
                required
                type="email"
              />
              <AppInput
                v-if="!isForgot"
                v-model="password"
                :autocomplete="isSignup ? 'new-password' : 'current-password'"
                label="Password"
                name="password"
                placeholder="••••••••"
                required
                type="password"
              />

              <p v-if="error" class="auth__error">{{ error }}</p>
              <p v-if="resetNotice" class="auth__notice">{{ resetNotice }}</p>

              <AppButton :disabled="submitting" :block="true" type="submit">
                {{ submitting ? "Working..." : submitLabel }}
              </AppButton>
            </form>

            <div class="app-form-grid auth__links">
              <template v-if="isLogin && !isAdmin">
                <RouterLink to="/auth/forgot-password">Forgot password?</RouterLink>
                <RouterLink to="/auth/signup">Create account</RouterLink>
              </template>
              <template v-else-if="isLogin && isAdmin">
                <RouterLink to="/auth/login">Back to user login</RouterLink>
              </template>
              <template v-else-if="isSignup">
                <RouterLink to="/auth/login">Already have an account?</RouterLink>
              </template>
              <template v-else>
                <RouterLink to="/auth/login">Back to login</RouterLink>
              </template>
            </div>
          </AppCard>
        </AppGrid>
      </PageSection>
    </AppPage>
  </div>
</template>

<style scoped>
.auth {
  position: relative;
  overflow: hidden;
  background:
    radial-gradient(circle at top right, rgba(35, 98, 255, 0.16), transparent 26rem),
    radial-gradient(circle at bottom left, rgba(15, 163, 177, 0.12), transparent 30rem),
    var(--color-background);
}

.auth__page {
  min-height: 100vh;
  --app-page-max-width: 1280px;
  padding-block: clamp(var(--space-6), 5vw, var(--space-12));
}

.auth__panel {
  align-items: center;
  gap: clamp(var(--space-6), 3vw, var(--space-10));
  grid-template-columns: minmax(0, 1.05fr) minmax(22rem, 35rem);
  width: min(100%, 1180px);
  margin: 0 auto;
}

.auth__intro,
.auth__card {
  min-height: 100%;
  min-width: 0;
}

.auth__intro {
  display: grid;
  gap: clamp(var(--space-6), 3vw, var(--space-10));
  align-content: center;
  padding: 0;
  padding-right: clamp(0px, 2vw, var(--space-8));
}

.auth__hero {
  display: grid;
  gap: var(--space-6);
  max-width: 36rem;
}

.auth__headline {
  display: grid;
  gap: var(--space-5);
}

.auth__brand {
  display: inline-flex;
  width: fit-content;
  font-family: var(--font-display);
  font-size: var(--type-title);
  font-weight: 700;
  letter-spacing: -0.03em;
}

.auth__headline .type-display {
  text-wrap: balance;
}

.auth__headline .type-body-lg {
  max-width: 24ch;
}

.auth__intro p,
.auth__notes p {
  color: var(--color-text-muted);
}

.auth__notes {
  display: grid;
  gap: var(--space-5);
  max-width: 40rem;
}

.auth__notes li {
  position: relative;
  display: grid;
  gap: var(--space-3);
  padding: var(--space-6) var(--space-6) var(--space-6) calc(var(--space-6) + var(--space-2));
  border: 1px solid rgba(15, 29, 58, 0.08);
  border-radius: var(--radius-lg);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.82), rgba(238, 243, 251, 0.94));
  box-shadow: 0 16px 40px rgba(15, 29, 58, 0.06);
  transition:
    transform var(--transition-base),
    box-shadow var(--transition-base),
    border-color var(--transition-base);
}

.auth__notes li::before {
  content: "";
  position: absolute;
  left: var(--space-4);
  top: var(--space-5);
  bottom: var(--space-5);
  width: 4px;
  border-radius: var(--radius-pill);
  background: linear-gradient(180deg, rgba(37, 99, 255, 0.88), rgba(36, 160, 237, 0.52));
}

.auth__notes li:hover {
  transform: translateY(-2px);
  box-shadow: 0 22px 48px rgba(15, 29, 58, 0.08);
  border-color: rgba(37, 99, 255, 0.16);
}

.auth__notes strong {
  font-size: 1rem;
  line-height: 1.35;
}

.auth__notes p {
  margin: 0;
  line-height: 1.6;
}

.auth__card {
  width: 100%;
  max-width: 35rem;
  justify-self: end;
  overflow: hidden;
}

.auth__card :deep(.app-card__header) {
  padding: clamp(var(--space-6), 3vw, 2.25rem) clamp(var(--space-6), 4vw, 2.5rem) 0;
}

.auth__card :deep(.app-card__header-copy) {
  gap: var(--space-3);
}

.auth__card :deep(.app-card__title) {
  font-size: clamp(1.625rem, 2.4vw, 2rem);
  letter-spacing: -0.03em;
}

.auth__card :deep(.app-card__subtitle) {
  max-width: 38ch;
  font-size: 0.95rem;
}

.auth__card :deep(.app-card__body) {
  height: 100%;
  align-content: start;
  gap: var(--space-6);
  padding: var(--space-6) clamp(var(--space-6), 4vw, 2.5rem) clamp(var(--space-6), 4vw, 2.25rem);
}

.auth__form {
  gap: var(--space-5);
}

.auth__form :deep(.app-field__label) {
  font-size: 0.95rem;
}

.auth__form :deep(.app-input) {
  min-height: 3.5rem;
  border-radius: 1.125rem;
  padding-inline: 1.125rem;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72);
}

.auth__form :deep(.app-input:hover) {
  border-color: var(--color-border-strong);
}

.auth__form :deep(.app-input:focus) {
  background: rgba(255, 255, 255, 0.98);
}

.auth__form :deep(.app-button) {
  min-height: 3.75rem;
  border-radius: 1.125rem;
  font-size: 1rem;
}

.auth__links a {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  min-height: 44px;
  color: var(--color-text-muted);
  transition:
    color var(--transition-fast),
    transform var(--transition-fast);
}

.auth__links a:hover {
  color: var(--color-primary);
  transform: translateX(2px);
}

.auth__links a:last-child {
  color: var(--color-text);
  font-weight: 600;
}

.auth__links {
  gap: var(--space-3);
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border);
}

.auth__error {
  margin: 0;
  color: var(--color-danger);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  background: var(--color-danger-soft);
}

.auth__notice {
  margin: 0;
  color: var(--color-warning);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  background: var(--color-warning-soft);
}

@media (max-width: 1023px) {
  .auth__panel {
    align-items: start;
    grid-template-columns: minmax(0, 1fr);
  }

  .auth__intro {
    padding-right: 0;
  }

  .auth__card {
    max-width: none;
    justify-self: stretch;
  }
}

@media (max-width: 767px) {
  .auth__page {
    padding-block: var(--space-5) var(--space-8);
  }

  .auth__panel,
  .auth__intro {
    gap: var(--space-6);
  }

  .auth__notes li {
    padding: var(--space-5) var(--space-5) var(--space-5) calc(var(--space-5) + var(--space-2));
  }

  .auth__notes li::before {
    left: var(--space-3);
    top: var(--space-4);
    bottom: var(--space-4);
  }

  .auth__card :deep(.app-card__header) {
    padding: var(--space-5) var(--space-5) 0;
  }

  .auth__card :deep(.app-card__body) {
    padding: var(--space-5);
  }
}
</style>
