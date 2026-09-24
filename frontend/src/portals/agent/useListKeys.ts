import { useEffect } from "react";

// Keys only act when nothing interactive has focus: not a field, a
// button/toggle, a select (role=combobox), or anything inside a menu/dialog.
const interactiveTarget = (el: EventTarget | null) =>
  el instanceof HTMLElement &&
  (el.isContentEditable ||
    ["INPUT", "TEXTAREA", "SELECT", "BUTTON"].includes(el.tagName) ||
    el.closest('[role="menu"], [role="dialog"], [role="listbox"], [role="combobox"], [role="button"]') !== null);

/** j/k move the selection, Enter opens it; ignored while typing or when a
 * menu/dialog has focus. */
export function useListKeys(
  count: number,
  selected: number,
  setSelected: (i: number) => void,
  open: (i: number) => void,
  enabled = true,
) {
  useEffect(() => {
    if (!enabled) return;
    function onKey(e: KeyboardEvent) {
      if (e.altKey || e.ctrlKey || e.metaKey || interactiveTarget(e.target) || count === 0) return;
      if (e.key === "j") {
        e.preventDefault();
        setSelected(Math.min(selected + 1, count - 1));
      } else if (e.key === "k") {
        e.preventDefault();
        setSelected(Math.max(selected - 1, 0));
      } else if (e.key === "Enter" && selected >= 0 && !(e.target instanceof HTMLAnchorElement)) {
        e.preventDefault();
        open(selected);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [count, selected, setSelected, open, enabled]);
}
