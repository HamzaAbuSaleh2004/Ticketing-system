import { describe, expect, it } from "vitest";
import { parseAnswer } from "./citations";
import { CUSTOMER_STATUS, relativeTime, replyMode, ticketRef } from "./tickets";

describe("replyMode (mirrors the backend's customer_reply_outcome)", () => {
  const now = new Date("2026-05-10T12:00:00Z");

  it("resolved reopens until reopen_until (from the server), then starts a new request", () => {
    const within = replyMode("resolved", "2026-05-08T12:00:00Z", "2026-05-11T12:00:00Z", now);
    expect(within).toMatchObject({ startsNew: false, action: "Reopen with reply" });
    expect(within.hint).toBe("Reply within 72h to reopen this request.");
    // A 24h window configured server-side is reflected in the copy.
    expect(replyMode("resolved", "2026-05-10T00:00:00Z", "2026-05-11T00:00:00Z", now).hint).toContain("24h");
    expect(replyMode("resolved", "2026-05-07T11:00:00Z", "2026-05-10T11:00:00Z", now)).toMatchObject({ startsNew: true });
  });

  it("closed always starts a new request", () => {
    expect(replyMode("closed", null, null, now)).toEqual({
      hint: "This request is closed. Replying starts a new request.",
      action: "Start a new request",
      startsNew: true,
    });
  });

  it("pending asks for the reply; active statuses have no hint", () => {
    expect(replyMode("pending", null, null, now).hint).toBe("We're waiting on your reply to continue.");
    expect(replyMode("in_progress", null, null, now)).toEqual({ hint: null, action: "Send reply", startsNew: false });
  });
});

describe("customer-facing status copy", () => {
  it("says 'Waiting on you' for pending", () => {
    expect(CUSTOMER_STATUS.pending.label).toBe("Waiting on you");
    expect(CUSTOMER_STATUS.new.line).toBe("We're reviewing this");
  });
});

describe("parseAnswer", () => {
  it("splits markers and drops out-of-range ones", () => {
    expect(parseAnswer("Reset it [1]. Links expire [2]. Bogus [3].", 2)).toEqual([
      { kind: "text", text: "Reset it" },
      { kind: "cite", n: 1 },
      { kind: "text", text: ". Links expire" },
      { kind: "cite", n: 2 },
      { kind: "text", text: ". Bogus" },
      { kind: "text", text: "." },
    ]);
  });
});

describe("formatting", () => {
  it("formats ticket refs and relative times", () => {
    expect(ticketRef(42)).toBe("TCK-00042");
    const now = new Date("2026-05-10T12:00:00Z");
    expect(relativeTime("2026-05-10T10:00:00Z", now)).toBe("2 hours ago");
    expect(relativeTime("2026-05-09T12:00:00Z", now)).toBe("yesterday");
    expect(relativeTime("2026-05-10T11:59:50Z", now)).toBe("just now");
  });
});
