import { describe, expect, it } from "vitest";
import { describeChange } from "./AdminPage";

describe("describeChange", () => {
  it("reads as before-to-after with human labels", () => {
    expect(describeChange({ diff_json: { before: { role: "agent", team: "tier1" }, after: { role: "end_user", team: null } } })).toBe(
      "Role Agent to End user, Team Tier 1 to none",
    );
    expect(describeChange({ diff_json: { after: { name: "Refunds", active: true } } })).toBe("Name Refunds, Active yes");
    expect(describeChange({ diff_json: null })).toBe("");
  });
});
