<script setup lang="ts">
import { computed, ref } from "vue";
import { RouterLink, useRouter } from "vue-router";

import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
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
      <AppGrid class="auth__panel" columns="2">
        <div class="auth__intro">
        <RouterLink class="auth__brand" to="/">TryApplyPilot</RouterLink>
        <AppBadge :tone="isAdmin ? 'warning' : 'primary'">
          {{ isAdmin ? "Admin Portal" : "User Portal" }}
        </AppBadge>
        <h1 class="type-display">{{ heading }}</h1>
        <p class="type-body-lg">{{ description }}</p>
        <ul class="auth__notes list-reset">
          <li>User login always lands on the job-seeker dashboard.</li>
          <li>Admin routes stay under <code>/admin/*</code> with role checks in the router.</li>
          <li>Telegram, resumes, companies, and preferences all stay on one shared account model.</li>
        </ul>
        </div>

        <AppCard class="auth__card">
          <form class="app-form-grid" @submit.prevent="handleSubmit">
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
}

.auth__panel {
  align-items: stretch;
}

.auth__intro,
.auth__card {
  min-height: 100%;
}

.auth__intro {
  display: grid;
  gap: var(--content-gap);
  align-content: center;
}

.auth__brand {
  font-family: var(--font-display);
  font-size: var(--type-title);
  font-weight: 700;
}

.auth__intro p,
.auth__notes li {
  color: var(--color-text-muted);
}

.auth__notes {
  display: grid;
  gap: var(--content-gap);
}

.auth__notes li {
  padding: var(--content-gap) var(--card-padding);
  border-radius: var(--card-radius);
  background: var(--color-surface-muted);
}

.auth__links a {
  color: var(--color-text-muted);
}

.auth__error {
  margin: 0;
  color: var(--color-danger);
}

.auth__notice {
  margin: 0;
  color: var(--color-warning);
}
</style>
