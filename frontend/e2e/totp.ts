import { createHmac } from "node:crypto";

// The seeded local demo accounts' published secret (backend app/seed.py).
export const DEMO_TOTP_SECRET = "LIVERXDEMOTOTPSECRETFORLOCALONLY";
const STEP_MS = 30_000;

function base32(secret: string): Buffer {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const ch of secret.replace(/[\s=]/g, "").toUpperCase()) bits += alphabet.indexOf(ch).toString(2).padStart(5, "0");
  const bytes = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) bytes.push(parseInt(bits.slice(i, i + 8), 2));
  return Buffer.from(bytes);
}

/** RFC 6238: 6 digits, 30 s, HMAC-SHA1. */
export function totpAt(secret: string, step: number): string {
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(step));
  const mac = createHmac("sha1", base32(secret)).update(counter).digest();
  const offset = mac[mac.length - 1] & 0xf;
  const n = (mac.readUInt32BE(offset) & 0x7fffffff) % 1_000_000;
  return String(n).padStart(6, "0");
}

// The API accepts each time step once per account (and one step of drift
// ahead), so repeat sign-ins of one account take the next unused step,
// waiting for the clock when both usable ones are spent. Playwright runs
// with one worker, so this module-level record sees every sign-in of this
// run; `withCode` covers steps an earlier run already used.
const lastStep = new Map<string, number>();

export async function nextCode(account: string, secret = DEMO_TOTP_SECRET): Promise<string> {
  const current = Math.floor(Date.now() / STEP_MS);
  let step = Math.max(current, (lastStep.get(account) ?? -Infinity) + 1);
  if (step > current + 1) {
    await new Promise((r) => setTimeout(r, (step - 1) * STEP_MS - Date.now() + 200));
    step = Math.max(Math.floor(Date.now() / STEP_MS), step);
  }
  lastStep.set(account, step);
  return totpAt(secret, step);
}

/** Tries codes until one is accepted: a code refused because an earlier run
 * already used its step moves on to the next step (at most 3 tries, well
 * under the API's 5-wrong-codes lockout). */
export async function withCode(account: string, attempt: (code: string) => Promise<boolean>, secret = DEMO_TOTP_SECRET) {
  for (let i = 0; i < 3; i++) {
    if (await attempt(await nextCode(account, secret))) return;
  }
  throw new Error(`no code accepted for ${account}`);
}
