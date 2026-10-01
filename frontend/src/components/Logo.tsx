import wordmarkUrl from "../assets/brand/liverx-logo.svg";
import iconUrl from "../assets/brand/liverx-icon.png";

/** The colour wordmark reads fine directly on a light surface (page 4 of the
 * brand guideline explicitly allows "colour logo on white") - the app is
 * light-only (Phase 25), so no dark-surface treatment is needed. */
export function LiverXWordmark({ height = 28 }: { height?: number }) {
  return <img src={wordmarkUrl} alt="LiverX" style={{ height, width: "auto", display: "block" }} />;
}

/** The X icon alone, for tight spaces (the agent nav rail). */
export function LiverXIcon({ size = 32 }: { size?: number }) {
  return <img src={iconUrl} alt="LiverX" style={{ height: size, width: "auto", display: "block" }} />;
}
