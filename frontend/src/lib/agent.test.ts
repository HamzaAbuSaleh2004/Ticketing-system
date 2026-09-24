import { describe, expect, it } from "vitest";
import { statusOptions } from "./lifecycle";
import { formatDuration, slaView, type SlaInput } from "./sla";

const CREATED = "2026-05-01T09:00:00Z";
const at = (iso: string) => Date.parse(iso);
const base: SlaInput = {
  status: "in_progress",
  created_at: CREATED,
  sla_response_due: "2026-05-01T10:00:00Z", // 1h
  sla_resolution_due: "2026-05-01T17:00:00Z", // 8h
  sla_paused_at: null,
  sla_paused_total_seconds: 0,
  first_responded_at: null,
};

describe("slaView", () => {
  it("runs the response clock until the first reply", () => {
    const v = slaView(base, at("2026-05-01T09:20:00Z"));
    expect(v).toMatchObject({ clock: "response", state: "on_track", countdown: "40m", stateLabel: null });
    expect(v.fraction).toBeCloseTo(40 / 60);
  });

  it("is at risk under 25% of the window, breached past due", () => {
    expect(slaView(base, at("2026-05-01T09:50:00Z"))).toMatchObject({ state: "at_risk", stateLabel: "At risk" });
    const late = slaView(base, at("2026-05-01T10:12:00Z"));
    expect(late).toMatchObject({ state: "breached", stateLabel: "Breached", countdown: "12m over", fraction: 0 });
    expect(late.description).toBe("First reply overdue by 12m");
  });

  it("switches to the resolution clock after the first reply, counting past pauses in the window", () => {
    const responded = { ...base, first_responded_at: "2026-05-01T09:05:00Z", sla_resolution_due: "2026-05-01T19:00:00Z", sla_paused_total_seconds: 2 * 3600 };
    // window = 10h - 2h paused = 8h; at 15:00, 4h left = 50%.
    const v = slaView(responded, at("2026-05-01T15:00:00Z"));
    expect(v).toMatchObject({ clock: "resolution", state: "on_track", countdown: "4h 00m" });
    expect(v.fraction).toBeCloseTo(0.5);
  });

  it("freezes while paused and says so in text", () => {
    const paused = { ...base, status: "pending" as const, first_responded_at: "2026-05-01T09:05:00Z", sla_paused_at: "2026-05-01T16:30:00Z" };
    const early = slaView(paused, at("2026-05-01T16:31:00Z"));
    const muchLater = slaView(paused, at("2026-05-03T09:00:00Z"));
    expect(early).toMatchObject({ state: "paused", stateLabel: "Paused", countdown: "30m" });
    expect(muchLater.countdown).toBe("30m");
    expect(muchLater.state).toBe("paused"); // never "breached" while paused
  });

  it("shows nothing once resolved or closed", () => {
    expect(slaView({ ...base, status: "resolved" }, at("2026-05-02T00:00:00Z")).state).toBe("none");
    expect(slaView({ ...base, status: "closed" }, at("2026-05-02T00:00:00Z")).state).toBe("none");
  });

  it("formats durations with tabular-friendly padding", () => {
    expect(formatDuration(3 * 3_600_000 + 5 * 60_000)).toBe("3h 05m");
    expect(formatDuration(26 * 3_600_000)).toBe("1d 2h");
    expect(formatDuration(30_000)).toBe("<1m");
  });
});

describe("statusOptions", () => {
  it("offers exactly the API's legal next statuses", () => {
    expect(statusOptions("in_progress", ["pending", "resolved"], 3).map((o) => o.value)).toEqual(["pending", "resolved"]);
    expect(statusOptions("closed", [], 3)).toEqual([]);
  });

  it("guards triaged → open until someone is assigned", () => {
    expect(statusOptions("triaged", ["open"], null)[0].disabledReason).toBe("Assign someone first");
    expect(statusOptions("triaged", ["open"], 7)[0].disabledReason).toBeNull();
  });
});
