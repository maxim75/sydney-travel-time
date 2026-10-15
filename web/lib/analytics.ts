import type { SiteData } from "./types";

declare global {
  interface Window { gtag?: (...args: unknown[]) => void; }
}

type Site = Pick<SiteData, "center" | "scale" | "localities" | "loc">;

export const hexagonClickParams = (site: Site, i: number, dataset: string) => ({
  latitude: +(site.center[2 * i + 1] / site.scale).toFixed(5),
  longitude: +(site.center[2 * i] / site.scale).toFixed(5),
  suburb: site.localities[site.loc[i]],
  dataset,
});

// Google Analytics event for a clicked or tapped hexagon
export function trackHexagonClick(site: Site, i: number, dataset: string): void {
  if (typeof window === "undefined" || typeof window.gtag !== "function") return;
  window.gtag("event", "hexagon_click", hexagonClickParams(site, i, dataset));
}
