import { describe, expect, it } from "vitest";
import { isAssistantReady } from "./local-status";

describe("isAssistantReady", () => {
  it("only enables the composer while the assistant is ready", () => {
    expect(isAssistantReady("Tayyor")).toBe(true);
    expect(isAssistantReady("Javob o‘ylanmoqda…")).toBe(false);
  });
});
