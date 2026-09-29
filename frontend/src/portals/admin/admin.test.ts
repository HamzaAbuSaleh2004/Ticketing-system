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

  it("reads sign-in security events as sentences", () => {
    expect(describeChange({ action: "user.2fa_reset", diff_json: { before: { two_factor_enabled: true }, after: { two_factor_enabled: false } } })).toBe(
      "Two-step verification reset",
    );
    expect(describeChange({ action: "user.recovery_code_used", diff_json: { remaining: 9 } } as never)).toBe(
      "Signed in with a recovery code, 9 left",
    );
  });
});
