import { chromium } from "@playwright/test";
import { createHmac } from "node:crypto";

function base32(s) {
  const A = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const ch of s.replace(/[\s=]/g, "").toUpperCase()) bits += A.indexOf(ch).toString(2).padStart(5, "0");
  const bytes = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) bytes.push(parseInt(bits.slice(i, i + 8), 2));
  return Buffer.from(bytes);
}
function code(secretStr, stepOffset = 0) {
  const step = Math.floor(Date.now() / 30000) + stepOffset;
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(step));
  const mac = createHmac("sha1", base32(secretStr)).update(counter).digest();
  const offset = mac[mac.length - 1] & 0xf;
  const n = (mac.readUInt32BE(offset) & 0x7fffffff) % 1_000_000;
  return String(n).padStart(6, "0");
}

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });

const email = `upload-check-${Date.now()}@example.com`;
await page.goto("http://localhost:8080/register");
await page.getByLabel("Name").fill("Upload Check");
await page.getByLabel("Email").fill(email);
await page.getByLabel("Password").fill("Password123!");
await page.getByRole("button", { name: "Create account" }).click();
const key = page.getByLabel("Setup key");
await key.waitFor({ timeout: 10000 });
const secret = (await key.innerText()).replace(/\s/g, "");
let enrolled = false;
for (let i = 0; i < 3 && !enrolled; i++) {
  await page.getByLabel("6-digit code").fill(code(secret, i));
  await page.getByRole("button", { name: "Turn on two-step verification" }).click();
  const recoveryBtn = page.getByRole("button", { name: "I've saved them, continue" });
  await recoveryBtn.waitFor({ timeout: 4000 }).then(() => { enrolled = true; }).catch(() => {});
}
await page.getByRole("button", { name: "I've saved them, continue" }).click();
await page.waitForURL(/\/$/, { timeout: 10000 });

const token = await page.evaluate(() => {
  for (const k of Object.keys(localStorage)) {
    try {
      const parsed = JSON.parse(localStorage.getItem(k));
      if (parsed?.access_token) return parsed.access_token;
      if (parsed?.state?.accessToken) return parsed.state.accessToken;
    } catch {}
  }
  return null;
});
console.log("token:", token ? token.slice(0, 20) + "..." : null);

const created = await page.request.post("http://localhost:8080/api/tickets", {
  headers: { Authorization: `Bearer ${token}` },
  data: { subject: "Upload check", description: "checking storage round trip" },
});
console.log("create ticket:", created.status());
const ticket = await created.json();

const upload = await page.request.post(`http://localhost:8080/api/tickets/${ticket.id}/attachments`, {
  headers: { Authorization: `Bearer ${token}` },
  multipart: { file: { name: "note.txt", mimeType: "text/plain", buffer: Buffer.from("hello prod-local storage") } },
});
console.log("upload:", upload.status());
const attachment = await upload.json();
console.log("attachment:", JSON.stringify(attachment));

const download = await page.request.get(`http://localhost:8080/api/attachments/${attachment.id}`, {
  headers: { Authorization: `Bearer ${token}` },
});
console.log("download:", download.status(), download.headers()["content-disposition"]);
const body = await download.body();
console.log("downloaded bytes match:", body.toString() === "hello prod-local storage");

await browser.close();
