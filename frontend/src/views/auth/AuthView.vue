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
              <AppInput v-if="isSignup" v-model="fullName" label="Full name" placeholder="Abhishek Kumar Jha" />
              <AppInput v-model="email" label="Email" type="email" placeholder="you@example.com" />
              <AppInput v-if="!isForgot" v-model="password" label="Password" type="password" placeholder="••••••••" />

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
  background:
    radial-gradient(circle at top right, rgba(35, 98, 255, 0.16), transparent 26rem),
    radial-gradient(circle at bottom left, rgba(15, 163, 177, 0.12), transparent 30rem),
    var(--color-background);
}

.auth__page {
  min-height: 100vh;
  --app-page-max-width: 1240px;
}

.auth__panel {
  align-items: stretch;
  width: min(100%, 1160px);
  margin: 0 auto;
}

.auth__intro,
.auth__card {
  min-height: 100%;
  min-width: 0;
}

.auth__intro {
  display: grid;
  gap: var(--space-8);
  align-content: center;
  padding: 0;
}

.auth__hero {
  display: grid;
  gap: var(--space-5);
  max-width: 34rem;
}

.auth__headline {
  display: grid;
  gap: var(--space-4);
}

.auth__brand {
  font-family: var(--font-display);
  font-size: var(--type-title);
  font-weight: 700;
}

.auth__intro p,
.auth__notes p {
  color: var(--color-text-muted);
}

.auth__notes {
  display: grid;
  gap: var(--space-4);
  max-width: 38rem;
}

.auth__notes li {
  display: grid;
  gap: var(--space-2);
  padding: var(--space-5) var(--space-6);
  border: 1px solid rgba(15, 29, 58, 0.06);
  border-radius: var(--radius-lg);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.72), rgba(238, 243, 251, 0.92));
  box-shadow: 0 10px 28px rgba(15, 29, 58, 0.05);
}

.auth__notes strong {
  font-size: var(--type-small);
  line-height: 1.35;
}

.auth__notes p {
  margin: 0;
  line-height: 1.6;
}

.auth__card {
  width: 100%;
  max-width: 34rem;
  justify-self: end;
}

.auth__card :deep(.app-card__body) {
  height: 100%;
  align-content: start;
  gap: var(--space-6);
}

.auth__form {
  gap: var(--space-4);
}

.auth__links a {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  color: var(--color-text-muted);
}

.auth__links {
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border);
}

.auth__error {
  margin: 0;
  color: var(--color-danger);
}

.auth__notice {
  margin: 0;
  color: var(--color-warning);
}

@media (max-width: 1023px) {
  .auth__card {
    max-width: none;
    justify-self: stretch;
  }
}

@media (max-width: 767px) {
  .auth__page {
    padding-block: var(--space-6) var(--space-8);
  }

  .auth__notes li {
    padding: var(--space-4) var(--space-5);
  }
}
</style>
