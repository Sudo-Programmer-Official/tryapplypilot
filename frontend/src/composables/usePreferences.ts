import { ref, watch, type Ref } from "vue";

import { saveUserPreferences, saveUserProfile } from "../api/user.api";
import type { AuthUser, UserPreferenceDraft } from "../types";
import { buildPreferencePayload, buildProfilePayload, cloneDraft, createPreferenceDraft } from "../utils/profile";

export function usePreferences(user: Ref<AuthUser | null>) {
  const draft = ref<UserPreferenceDraft>(createPreferenceDraft(user.value));
  const saving = ref(false);
  const error = ref<string | null>(null);

  watch(
    user,
    (nextUser) => {
      draft.value = createPreferenceDraft(nextUser);
    },
    { immediate: true },
  );

  function reset(): void {
    draft.value = createPreferenceDraft(user.value);
  }

  async function saveProfile(onSuccess: (nextUser: AuthUser) => void): Promise<void> {
    saving.value = true;
    error.value = null;
    try {
      const payload = await saveUserProfile(buildProfilePayload(cloneDraft(draft.value)));
      onSuccess(payload.user);
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to save profile.";
      throw err;
    } finally {
      saving.value = false;
    }
  }

  async function savePreferences(onSuccess: (nextUser: AuthUser) => void): Promise<void> {
    saving.value = true;
    error.value = null;
    try {
      const payload = await saveUserPreferences(buildPreferencePayload(cloneDraft(draft.value)));
      onSuccess(payload.user);
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to save preferences.";
      throw err;
    } finally {
      saving.value = false;
    }
  }

  return {
    draft,
    saving,
    error,
    reset,
    saveProfile,
    savePreferences,
  };
}
