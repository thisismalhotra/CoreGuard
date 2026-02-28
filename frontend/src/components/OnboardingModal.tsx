"use client";

import { useState, useRef, useEffect } from "react";
import {
  Shield,
  Zap,
  DollarSign,
  ArrowRight,
  ArrowLeft,
  X,
  ChevronRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const STORAGE_KEY = "cg_onboarding_seen";

const AGENT_CHAIN = [
  { name: "Aura", role: "Demand Sensing", color: "bg-purple-600" },
  { name: "Dispatcher", role: "Triage & Priority", color: "bg-cyan-600" },
  { name: "Core-Guard", role: "MRP Logic", color: "bg-blue-600" },
  { name: "Ghost-Writer", role: "Procurement", color: "bg-emerald-600" },
  { name: "Eagle-Eye", role: "Quality Inspection", color: "bg-orange-600" },
];

type Slide = {
  icon: React.ReactNode;
  title: string;
  content: React.ReactNode;
};

const slides: Slide[] = [
  {
    icon: <Shield className="h-10 w-10 text-blue-400" />,
    title: "Welcome to Core-Guard",
    content: (
      <div className="space-y-3 text-sm text-muted-foreground">
        <p>
          Core-Guard is an <span className="text-foreground font-medium">autonomous supply chain OS</span> for the
          FL-001 Flashlight. Five AI agents monitor inventory, detect shortages,
          and execute Purchase Orders — without manual intervention.
        </p>
        <p>
          This is a <span className="text-blue-400 font-medium">Glass Box</span> system: every agent decision is
          logged and streamed to your dashboard in real-time. Nothing happens
          behind the scenes.
        </p>
      </div>
    ),
  },
  {
    icon: <ChevronRight className="h-10 w-10 text-cyan-400" />,
    title: "5 Autonomous Agents, One Chain",
    content: (
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          When a disruption occurs, agents fire in sequence — each handing off to
          the next:
        </p>
        <div className="flex flex-col gap-2">
          {AGENT_CHAIN.map((agent, i) => (
            <div key={agent.name} className="flex items-center gap-3">
              {i > 0 && (
                <div className="ml-[52px] -mt-3 mb-1 w-px h-2 bg-border" />
              )}
              <div className="flex items-center gap-3">
                <Badge
                  className={`${agent.color} text-white text-xs w-[110px] justify-center shrink-0`}
                >
                  {agent.name}
                </Badge>
                <span className="text-xs text-muted-foreground">{agent.role}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    ),
  },
  {
    icon: <Zap className="h-10 w-10 text-yellow-400" />,
    title: "Inject Chaos. Watch Agents React.",
    content: (
      <div className="space-y-3 text-sm text-muted-foreground">
        <p>
          The <span className="text-foreground font-medium">God Mode</span> tab gives you 6 chaos scenarios to
          trigger — from a 300% demand spike to a full supplier blackout.
        </p>
        <ol className="list-decimal list-inside space-y-1.5 text-xs">
          <li>Go to the <span className="text-yellow-400 font-medium">God Mode</span> tab</li>
          <li>Pick a scenario (e.g. <span className="font-medium text-foreground/80">300% Demand Spike</span>)</li>
          <li>Click <span className="font-medium text-foreground/80">Inject Chaos</span></li>
          <li>Watch agent logs stream live in the <span className="text-blue-400 font-medium">Live Logs</span> tab</li>
        </ol>
        <p>
          Results (POs, inspections) appear in the{" "}
          <span className="text-foreground font-medium">Digital Dock</span> tab.
        </p>
      </div>
    ),
  },
  {
    icon: <DollarSign className="h-10 w-10 text-pink-400" />,
    title: "Guardrails You Can Trust",
    content: (
      <div className="space-y-3 text-sm text-muted-foreground">
        <p>
          Core-Guard has a hard-coded{" "}
          <span className="text-foreground font-medium">Financial Constitution</span>: any
          Purchase Order exceeding{" "}
          <span className="text-pink-400 font-medium">$5,000</span> is automatically
          blocked as <span className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded text-foreground/80">PENDING_APPROVAL</span>.
        </p>
        <p>
          No agent — not even an LLM — can override this rule. You review and
          approve (or reject) flagged POs directly in the{" "}
          <span className="text-foreground font-medium">Digital Dock</span> tab.
        </p>
        <p className="text-xs border border-border bg-card rounded-lg px-3 py-2">
          Try the <span className="text-pink-400 font-medium">Constitution Breach</span> scenario in God Mode to see
          this guardrail fire in action.
        </p>
      </div>
    ),
  },
];

// Lazy initializer reads localStorage only on the client — safe with "use client"
function shouldShowOnboarding() {
  if (typeof window === "undefined") return false;
  return !localStorage.getItem(STORAGE_KEY);
}

export function OnboardingModal() {
  const [visible, setVisible] = useState(shouldShowOnboarding);
  const [slide, setSlide] = useState(0);
  const modalRef = useRef<HTMLDivElement>(null);

  const dismiss = () => {
    localStorage.setItem(STORAGE_KEY, "true");
    setVisible(false);
  };

  useEffect(() => {
    if (!visible) return;
    const modal = modalRef.current;
    if (!modal) return;

    const focusableElements = modal.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    const first = focusableElements[0] as HTMLElement;
    const last = focusableElements[focusableElements.length - 1] as HTMLElement;

    const handleTab = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return;
      if (e.shiftKey) {
        if (document.activeElement === first) { e.preventDefault(); last?.focus(); }
      } else {
        if (document.activeElement === last) { e.preventDefault(); first?.focus(); }
      }
    };

    document.addEventListener("keydown", handleTab);
    first?.focus();
    return () => document.removeEventListener("keydown", handleTab);
  }, [visible]);

  if (!visible) return null;

  const isFirst = slide === 0;
  const isLast = slide === slides.length - 1;
  const current = slides[slide];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      // Intentionally not closeable by clicking backdrop — first-visit modal requires explicit action
    >
      <div ref={modalRef} className="bg-background border border-border rounded-2xl shadow-2xl w-full max-w-md flex flex-col">
        {/* Skip button */}
        <div className="flex justify-end px-5 pt-4">
          <button
            onClick={dismiss}
            className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors"
            aria-label="Skip onboarding"
          >
            <X className="h-3 w-3" />
            Skip
          </button>
        </div>

        {/* Slide content */}
        <div className="px-6 pb-2 flex flex-col items-center text-center gap-4 min-h-[320px] justify-center">
          {current.icon}
          <h2 className="text-lg font-semibold tracking-tight text-foreground">
            {current.title}
          </h2>
          <div className="text-left w-full">{current.content}</div>
        </div>

        {/* Progress dots */}
        <div className="flex justify-center gap-1.5 py-4">
          {slides.map((_, i) => (
            <button
              key={i}
              onClick={() => setSlide(i)}
              className={`h-1.5 rounded-full transition-all ${
                i === slide
                  ? "w-4 bg-blue-400"
                  : i < slide
                  ? "w-1.5 bg-blue-400/40"
                  : "w-1.5 bg-muted"
              }`}
              aria-label={`Go to slide ${i + 1}`}
            />
          ))}
        </div>

        {/* Navigation */}
        <div className="flex items-center justify-between px-6 pb-6 gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setSlide((s) => s - 1)}
            disabled={isFirst}
            className="gap-1.5 text-xs"
          >
            <ArrowLeft className="h-3 w-3" />
            Back
          </Button>

          {isLast ? (
            <Button
              size="sm"
              onClick={dismiss}
              className="gap-1.5 text-xs bg-blue-600 hover:bg-blue-500 text-white"
            >
              Let&apos;s Go
              <ArrowRight className="h-3 w-3" />
            </Button>
          ) : (
            <Button
              size="sm"
              onClick={() => setSlide((s) => s + 1)}
              className="gap-1.5 text-xs bg-blue-600 hover:bg-blue-500 text-white"
            >
              Next
              <ArrowRight className="h-3 w-3" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
