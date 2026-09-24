import { apiBlob } from "../api/client";

/** Attachments need the bearer token, so a plain <a href> can't fetch them. */
export async function downloadAttachment(id: number, filename: string): Promise<void> {
  const url = URL.createObjectURL(await apiBlob(`/attachments/${id}`));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Revoking synchronously can cancel the download in some browsers.
  window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
}
