<script setup lang="ts">
import { computed, ref } from "vue";

import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import PageSection from "../../components/layout/PageSection.vue";
import AppBadge from "../../components/ui/AppBadge.vue";
import AppButton from "../../components/ui/AppButton.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppInput from "../../components/ui/AppInput.vue";
import AppTextArea from "../../components/ui/AppTextArea.vue";
import { createTelegramConnectSession, verifyTelegramConnection } from "../../api/telegram.api";
import { useAuth } from "../../composables/useAuth";
import { usePreferences } from "../../composables/usePreferences";
import { useToast } from "../../composables/useToast";
import type { TelegramConnectSession } from "../../types";
import { formatDateTime } from "../../utils/format";

const auth = useAuth();
const { pushToast } = useToast();
const { draft, saving, saveProfile: persistProfile } = usePreferences(auth.user);

const connectSession = ref<TelegramConnectSession | null>(null);
const connecting = ref(false);
const verifying = ref(false);

const telegramStatus = computed(() => (auth.user.value?.telegram_chat_id ? "Connected" : "Pending"));

async function handleSaveProfile(): Promise<void> {
  await persistProfile(auth.setUser);
  pushToast("Profile saved", "Your profile metadata is ready for matching and onboarding.", "success");
}

async function startTelegramConnect(): Promise<void> {
  connecting.value = true;
  try {
    connectSession.value = await createTelegramConnectSession();
    pushToast(
      "Telegram session created",
      "Open the exact bot link, press Start in Telegram, then verify here. If the bot chat already existed, paste the manual /start command shown below. Sending a normal message like 'hi' will not connect the chat.",
      "info",
    );
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to create Telegram session.";
    pushToast("Telegram setup failed", message, "error");
  } finally {
    connecting.value = false;
  }
}

async function verifyTelegram(): Promise<void> {
  if (!connectSession.value) {
    return;
  }
  verifying.value = true;
  try {
    const payload = await verifyTelegramConnection(connectSession.value.connect_token);
    auth.setUser(payload.user);
    if (payload.connected && payload.user.telegram_chat_id) {
      pushToast("Telegram connected", "You will now receive private job alerts.", "success");
      connectSession.value = null;
      return;
    }
    pushToast(
      "Telegram still pending",
      payload.message ?? "Open the exact bot link, press Start in Telegram, then verify the connection again.",
      "info",
    );
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to verify Telegram connection.";
    pushToast("Telegram verification failed", message, "error");
  } finally {
    verifying.value = false;
  }
}
</script>

<template>
  <AppPage>
    <PageHeader
      title="Profile"
      description="Keep your account details current and connect Telegram so the notification pipeline can deliver alerts privately."
    >
      <template #actions>
        <AppButton :disabled="saving" @click="handleSaveProfile">{{ saving ? "Saving..." : "Save profile" }}</AppButton>
      </template>
    </PageHeader>

    <PageSection>
      <AppGrid columns="2" class="profile-grid">
        <AppCard class="profile-panel" title="Personal profile" subtitle="This information powers onboarding progress and future resume workflows.">
          <div class="app-form-grid">
            <AppInput v-model="draft.full_name" autocomplete="name" label="Full name" name="fullName" placeholder="Abhishek Kumar Jha" />
            <AppInput
              v-model="draft.linkedin_url"
              :spellcheck="false"
              autocomplete="url"
              label="LinkedIn URL"
              name="linkedinUrl"
              placeholder="https://linkedin.com/in/..."
              type="url"
            />
            <AppInput
              v-model="draft.github_url"
              :spellcheck="false"
              autocomplete="url"
              label="GitHub URL"
              name="githubUrl"
              placeholder="https://github.com/..."
              type="url"
            />
            <AppInput
              v-model="draft.portfolio_url"
              :spellcheck="false"
              autocomplete="url"
              label="Portfolio URL"
              name="portfolioUrl"
              placeholder="https://..."
              type="url"
            />
            <AppInput
              :model-value="draft.years_of_experience ?? ''"
              label="Years of experience"
              name="yearsOfExperience"
              type="number"
              :min="0"
              @update:model-value="draft.years_of_experience = $event ? Number($event) : null"
            />
            <AppInput v-model="draft.work_authorization" label="Work authorization" name="workAuthorization" placeholder="US citizen, H1B, EAD..." />
            <AppInput v-model="draft.visa_status" label="Visa status" name="visaStatus" placeholder="Optional" />
          </div>
        </AppCard>

        <div class="app-stack app-stack--card">
          <AppCard class="profile-panel" title="Telegram delivery" subtitle="Each user connects directly to the bot for private alerts.">
            <div class="profile-status-row">
              <AppBadge :tone="auth.user.value?.telegram_chat_id ? 'success' : 'warning'">{{ telegramStatus }}</AppBadge>
              <span v-if="auth.user.value?.telegram_chat_id" class="profile-status-pill">Chat ID {{ auth.user.value.telegram_chat_id }}</span>
            </div>
            <div class="profile-actions">
              <AppButton variant="secondary" :disabled="connecting" @click="startTelegramConnect">
                {{ connecting ? "Starting..." : auth.user.value?.telegram_chat_id ? "Reconnect Telegram" : "Connect Telegram" }}
              </AppButton>
              <AppButton :disabled="!connectSession || verifying" @click="verifyTelegram">
                {{ verifying ? "Verifying..." : "Verify connection" }}
              </AppButton>
            </div>
            <AppTextArea
              v-if="connectSession"
              :model-value="connectSession.connect_url"
              label="Bot link"
              hint="Open this exact link, press Start in Telegram, then return here and click verify. If the bot chat was already open before, use the manual command below instead."
              readonly
              :rows="3"
              @update:model-value="() => undefined"
            />
            <AppTextArea
              v-if="connectSession?.connect_command"
              :model-value="connectSession.connect_command"
              label="Manual connect command"
              hint="If Telegram opens an existing chat and does not trigger the deep link, send this exact command to the bot, then click verify."
              readonly
              :rows="2"
              @update:model-value="() => undefined"
            />
          </AppCard>

          <AppCard class="profile-panel" title="Account status" subtitle="Basic metadata for support and operations.">
            <div class="app-meta-grid profile-meta-grid">
              <div class="profile-meta-card">
                <span class="eyebrow">Email</span>
                <strong>{{ auth.user.value?.email }}</strong>
              </div>
              <div class="profile-meta-card">
                <span class="eyebrow">Role</span>
                <strong>{{ auth.user.value?.role }}</strong>
              </div>
              <div class="profile-meta-card">
                <span class="eyebrow">Created</span>
                <strong>{{ formatDateTime(auth.user.value?.created_at) }}</strong>
              </div>
              <div class="profile-meta-card">
                <span class="eyebrow">Last login</span>
                <strong>{{ formatDateTime(auth.user.value?.last_login_at) }}</strong>
              </div>
            </div>
          </AppCard>
        </div>
      </AppGrid>
    </PageSection>
  </AppPage>
</template>

<style scoped>
.profile-grid {
  align-items: stretch;
}

.profile-panel {
  min-height: 100%;
}

.profile-panel :deep(.app-card__header) {
  padding: clamp(var(--space-6), 3vw, 2.25rem) clamp(var(--space-6), 4vw, 2.5rem) 0;
}

.profile-panel :deep(.app-card__header-copy) {
  gap: var(--space-3);
}

.profile-panel :deep(.app-card__title) {
  font-size: clamp(1.625rem, 2.3vw, 2rem);
  letter-spacing: -0.03em;
}

.profile-panel :deep(.app-card__subtitle) {
  max-width: 42ch;
  font-size: 0.98rem;
}

.profile-panel :deep(.app-card__body) {
  align-content: start;
  gap: var(--space-6);
  padding: var(--space-6) clamp(var(--space-6), 4vw, 2.5rem) clamp(var(--space-6), 4vw, 2.25rem);
}

.profile-panel :deep(.app-form-grid) {
  gap: var(--space-5);
}

.profile-panel :deep(.app-field__label) {
  font-size: 0.95rem;
}

.profile-panel :deep(.app-input),
.profile-panel :deep(.app-textarea) {
  min-height: 3.5rem;
  border-radius: 1.125rem;
  padding-inline: 1.125rem;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72);
}

.profile-panel :deep(.app-textarea) {
  min-height: 6.5rem;
  padding-block: 1rem;
}

.profile-panel :deep(.app-input:hover),
.profile-panel :deep(.app-textarea:hover) {
  border-color: var(--color-border-strong);
}

.profile-panel :deep(.app-input:focus),
.profile-panel :deep(.app-textarea:focus) {
  background: rgba(255, 255, 255, 0.98);
}

.profile-panel :deep(.app-button) {
  min-height: 3.25rem;
  border-radius: 1rem;
}

.profile-status-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3);
}

.profile-status-pill {
  display: inline-flex;
  align-items: center;
  min-height: 2.5rem;
  padding: 0 var(--space-4);
  border: 1px solid rgba(15, 29, 58, 0.08);
  border-radius: var(--radius-pill);
  background: rgba(255, 255, 255, 0.72);
  color: var(--color-text-muted);
  font-size: 0.95rem;
}

.profile-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3);
}

.profile-actions :deep(.app-button) {
  min-width: 11rem;
}

.profile-meta-grid {
  gap: var(--space-4);
}

.profile-meta-card {
  padding: var(--space-5);
  border: 1px solid rgba(15, 29, 58, 0.08);
  border-radius: var(--radius-lg);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.88), rgba(246, 249, 253, 0.96));
  box-shadow: 0 12px 26px rgba(15, 29, 58, 0.04);
}

.profile-meta-card .eyebrow {
  display: block;
}

.app-meta-grid strong {
  display: block;
  margin-top: var(--space-2);
  font-size: 1rem;
  line-height: 1.35;
}

@media (max-width: 767px) {
  .profile-panel :deep(.app-card__header) {
    padding: var(--space-5) var(--space-5) 0;
  }

  .profile-panel :deep(.app-card__body) {
    padding: var(--space-5);
  }

  .profile-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .profile-actions :deep(.app-button) {
    min-width: 0;
  }

  .profile-meta-card {
    padding: var(--space-4);
  }
}
</style>
