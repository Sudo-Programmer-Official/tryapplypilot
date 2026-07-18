import { readonly, ref } from "vue";

import type { ToastMessage, ToastTone } from "../types";

const messages = ref<ToastMessage[]>([]);

export function useToast() {
  function pushToast(title: string, description = "", tone: ToastTone = "info"): void {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    messages.value = [...messages.value, { id, title, description, tone }];
    window.setTimeout(() => dismissToast(id), 4200);
  }

  function dismissToast(id: string): void {
    messages.value = messages.value.filter((message) => message.id !== id);
  }

  return {
    toasts: readonly(messages),
    pushToast,
    dismissToast,
  };
}
