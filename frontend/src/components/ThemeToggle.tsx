"use client";

import { useTheme } from "next-themes";
import { useEffect, useState, useRef } from "react";
import { Sun, Moon } from "lucide-react";

const THEMES = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
] as const;

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Hydration guard: set mounted flag once client-side rendering begins.
  // eslint-disable-next-line react-hooks/set-state-in-effect -- standard hydration pattern
  useEffect(() => setMounted(true), []);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (!mounted) return null;

  const current = THEMES.find((t) => t.value === theme) || THEMES[1];
  const Icon = current.icon;

  return (
    <div className="relative" ref={ref}>
      <button
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md
                   border border-input text-muted-foreground
                   hover:text-foreground hover:border-foreground/30
                   transition-colors cursor-pointer"
        onClick={() => setOpen(!open)}
        aria-label={`Theme: ${current.label}`}
        aria-expanded={open}
        aria-haspopup="listbox"
      >
        <Icon className="h-3.5 w-3.5" />
        {current.label}
      </button>
      {open && (
        <div
          className="absolute right-0 top-full mt-1 z-50 bg-card border border-border
                        rounded-md shadow-lg py-1 min-w-[130px]"
          role="listbox"
          aria-label="Theme options"
        >
          {THEMES.map(({ value, label, icon: ThemeIcon }) => (
            <button
              key={value}
              role="option"
              aria-selected={theme === value}
              className={`w-full flex items-center gap-2 px-3 py-1.5 text-xs cursor-pointer
                         hover:bg-muted transition-colors
                         ${theme === value ? "text-foreground font-medium" : "text-muted-foreground"}`}
              onClick={() => {
                setTheme(value);
                setOpen(false);
              }}
            >
              <ThemeIcon className="h-3.5 w-3.5" />
              {label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
