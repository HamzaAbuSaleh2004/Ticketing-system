export type AnswerPart = { kind: "text"; text: string } | { kind: "cite"; n: number };

/** Splits a grounded answer into text and [n] citation markers. The API
 * already renumbered markers to 1..sources.length; anything outside that
 * range is dropped rather than shown as a dangling marker. */
export function parseAnswer(answer: string, sourceCount: number): AnswerPart[] {
  const parts: AnswerPart[] = [];
  const re = /\s*\[(\d+)\]/g;
  let last = 0;
  for (let m = re.exec(answer); m; m = re.exec(answer)) {
    if (m.index > last) parts.push({ kind: "text", text: answer.slice(last, m.index) });
    const n = Number(m[1]);
    if (n >= 1 && n <= sourceCount) parts.push({ kind: "cite", n });
    last = m.index + m[0].length;
  }
  if (last < answer.length) parts.push({ kind: "text", text: answer.slice(last) });
  return parts;
}
