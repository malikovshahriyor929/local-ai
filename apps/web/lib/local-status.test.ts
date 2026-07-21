import { describe, expect, it } from "vitest";
import { isAssistantReady } from "./local-status";

describe("isAssistantReady", () => {
  it("enables the composer while the assistant is idle", () => {
    expect(isAssistantReady("Tayyor")).toBe(true);
  });

  it("keeps the composer usable while an answer is being read aloud", () => {
    expect(isAssistantReady("Javob o‘qilmoqda…")).toBe(true);
  });

  it("blocks the composer while the assistant is still working", () => {
    expect(isAssistantReady("Javob o‘ylanmoqda…")).toBe(false);
    expect(isAssistantReady("Buyruq bajarilmoqda…")).toBe(false);
    expect(isAssistantReady("Ovoz yaratilmoqda…")).toBe(false);
    expect(isAssistantReady("Matnga aylantirilmoqda…")).toBe(false);
  });
});
