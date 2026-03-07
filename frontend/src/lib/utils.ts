import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import { useEffect, useState } from "react"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Resolve a CSS custom property to its computed color value (works in SVG/Recharts). */
export function useCSSColor(varName: string, fallback = "#888"): string {
  const [color, setColor] = useState(fallback);
  useEffect(() => {
    const raw = getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
    if (raw) setColor(raw.startsWith("oklch") || raw.startsWith("#") || raw.startsWith("rgb") ? raw : `hsl(${raw})`);
  }, [varName]);
  // Re-resolve on theme change (class mutation on <html>)
  useEffect(() => {
    const observer = new MutationObserver(() => {
      const raw = getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
      if (raw) setColor(raw.startsWith("oklch") || raw.startsWith("#") || raw.startsWith("rgb") ? raw : `hsl(${raw})`);
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, [varName]);
  return color;
}
