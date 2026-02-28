"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[CoreGuard] Root layout error:", error);
  }, [error]);

  return (
    <html lang="en">
      <body className="flex min-h-screen items-center justify-center bg-gray-950 px-4 text-white">
        <div className="flex max-w-md flex-col items-center gap-6 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-red-500/10">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-8 w-8 text-red-400"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3" />
              <path d="M12 9v4" />
              <path d="M12 17h.01" />
            </svg>
          </div>

          <div className="space-y-2">
            <h1 className="text-2xl font-bold tracking-tight">
              Critical Error
            </h1>
            <p className="text-sm text-gray-400">
              {error.message || "A critical error occurred in the application."}
            </p>
            {error.digest && (
              <p className="text-xs text-gray-500">
                Error ID: {error.digest}
              </p>
            )}
          </div>

          <button
            onClick={() => reset()}
            className="rounded-md bg-white px-4 py-2 text-sm font-medium text-gray-950 transition-colors hover:bg-gray-200"
          >
            Try Again
          </button>
        </div>
      </body>
    </html>
  );
}
