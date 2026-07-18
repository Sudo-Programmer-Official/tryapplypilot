<script setup lang="ts">
import { computed, ref } from "vue";

import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
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
    pushToast("Telegram session created", "Open the bot link, press Start, then verify the connection here.", "info");
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
    pushToast("Telegram connected", "You will now receive private job alerts.", "success");
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

    <AppGrid as="section" columns="2">
      <AppCard title="Personal profile" subtitle="This information powers onboarding progress and future resume workflows.">
        <div class="app-form-grid">
          <AppInput v-model="draft.full_name" label="Full name" placeholder="Abhishek Kumar Jha" />
          <AppInput v-model="draft.linkedin_url" label="LinkedIn URL" placeholder="https://linkedin.com/in/..." />
          <AppInput v-model="draft.github_url" label="GitHub URL" placeholder="https://github.com/..." />
          <AppInput v-model="draft.portfolio_url" label="Portfolio URL" placeholder="https://..." />
          <AppInput
            :model-value="draft.years_of_experience ?? ''"
            label="Years of experience"
            type="number"
            :min="0"
            @update:model-value="draft.years_of_experience = $event ? Number($event) : null"
          />
          <AppInput v-model="draft.work_authorization" label="Work authorization" placeholder="US citizen, H1B, EAD..." />
          <AppInput v-model="draft.visa_status" label="Visa status" placeholder="Optional" />
        </div>
      </AppCard>

      <div class="app-stack app-stack--card">
        <AppCard title="Telegram delivery" subtitle="Each user connects directly to the bot for private alerts.">
          <div class="app-actions-row">
            <AppBadge :tone="auth.user.value?.telegram_chat_id ? 'success' : 'warning'">{{ telegramStatus }}</AppBadge>
            <span v-if="auth.user.value?.telegram_chat_id">Chat ID {{ auth.user.value.telegram_chat_id }}</span>
          </div>
          <div class="app-actions-row">
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
            hint="Open this link, press Start in Telegram, then return here and click verify."
            :rows="3"
            @update:model-value="() => undefined"
          />
        </AppCard>

        <AppCard title="Account status" subtitle="Basic metadata for support and operations.">
          <div class="app-meta-grid">
            <div>
              <span class="eyebrow">Email</span>
              <strong>{{ auth.user.value?.email }}</strong>
            </div>
            <div>
              <span class="eyebrow">Role</span>
              <strong>{{ auth.user.value?.role }}</strong>
            </div>
            <div>
              <span class="eyebrow">Created</span>
              <strong>{{ formatDateTime(auth.user.value?.created_at) }}</strong>
            </div>
            <div>
              <span class="eyebrow">Last login</span>
              <strong>{{ formatDateTime(auth.user.value?.last_login_at) }}</strong>
            </div>
          </div>
        </AppCard>
      </div>
    </AppGrid>
  </AppPage>
</template>

<style scoped>
.app-meta-grid strong {
  display: block;
  margin-top: var(--space-2);
}
</style>
