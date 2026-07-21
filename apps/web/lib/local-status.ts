// Playback is not work in progress: a user who already knows what to ask next
// should not have to wait for the previous answer to finish being read aloud.
const READY_STATUSES = new Set(["Tayyor", "Javob o‘qilmoqda…"]);

export function isAssistantReady(status: string) {
  return READY_STATUSES.has(status);
}
