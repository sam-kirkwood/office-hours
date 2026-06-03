"use client";

import { useEffect, useState } from "react";

// Returns true on viewports narrower than Tailwind's `md` breakpoint (768 px).
// Used only by the two graph surfaces that need a list-view fallback
// (SkillTreeShell + ConfirmGraph). Everything else in the app is already
// responsive via existing `sm:` rules.
//
// SSR-safe: returns false during server render and on first paint, then
// updates on mount. A one-frame flash on first load is acceptable here —
// both call sites are below-the-fold client islands.

export function useIsMobile(maxWidthPx = 767): boolean {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const mql = window.matchMedia(`(max-width: ${maxWidthPx}px)`);
    const update = () => setIsMobile(mql.matches);
    update();
    mql.addEventListener("change", update);
    return () => mql.removeEventListener("change", update);
  }, [maxWidthPx]);

  return isMobile;
}
