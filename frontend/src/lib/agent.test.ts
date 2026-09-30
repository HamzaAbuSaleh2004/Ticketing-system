import { describe, expect, it } from "vitest";
import { statusOptions } from "./lifecycle";
import { formatDuration, waitingOnText } from "./tickets";

describe("waitingOnText", () => {
  it("names each side with an open count, or null when both are clear", () => {
    expect(waitingOnText(0, 0)).toBeNull();
    expect(waitingOnText(2, 0)).toBe("Customer 2");
    expect(waitingOnText(0, 1)).toBe("LiverX 1");
    expect(waitingOnText(1, 2)).toBe("Customer 1, LiverX 2");
  });
});

describe("formatDuration", () => {
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

  it("guards open → in_progress until someone is assigned", () => {
    expect(statusOptions("open", ["in_progress"], null)[0].disabledReason).toBe("Assign someone first");
    expect(statusOptions("open", ["in_progress"], 7)[0].disabledReason).toBeNull();
  });
});
