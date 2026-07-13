import { useEffect, useState } from "react";

/**
 * Whether heavy decorative effects (the 3D particle background, custom cursor)
 * should run. They are disabled when the user prefers reduced motion OR is on a
 * coarse pointer (touch / mobile) — where a full-screen r3f render loop drains
 * battery, janks scroll, and a custom cursor is dead weight (or a double cursor).
 *
 * Defaults to `false` so nothing heavy mounts on the first paint or on
 * touch/reduced-motion devices; it flips on only for fine-pointer, motion-OK
 * displays after mount.
 */
export function useHeavyFxEnabled(): boolean {
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
    const coarse = window.matchMedia("(pointer: coarse)");
    const compute = () => setEnabled(!reduce.matches && !coarse.matches);
    compute();
    reduce.addEventListener("change", compute);
    coarse.addEventListener("change", compute);
    return () => {
      reduce.removeEventListener("change", compute);
      coarse.removeEventListener("change", compute);
    };
  }, []);

  return enabled;
}
