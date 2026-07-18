import type { TelegramConnectSession, TelegramVerifyResult } from "../types";
import { requestJson } from "./client";

export function createTelegramConnectSession(): Promise<TelegramConnectSession> {
  return requestJson<TelegramConnectSession>("/api/auth/me/telegram/connect", {
    method: "POST",
  });
}

export function verifyTelegramConnection(connectToken: string): Promise<TelegramVerifyResult> {
  return requestJson<TelegramVerifyResult>("/api/auth/me/telegram/verify", {
    method: "POST",
    body: JSON.stringify({ connect_token: connectToken }),
  });
}
