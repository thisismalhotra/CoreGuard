import { io, Socket } from "socket.io-client";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

// Use globalThis to survive Next.js HMR (Hot Module Replacement).
// Without this, each HMR update creates a new socket connection,
// leaking the previous one and causing duplicate event handlers.
const globalForSocket = globalThis as unknown as {
  __coreGuardSocket?: Socket;
};

export function getSocket(): Socket {
  if (!globalForSocket.__coreGuardSocket) {
    globalForSocket.__coreGuardSocket = io(BACKEND_URL, {
      transports: ["websocket", "polling"],
      autoConnect: false,
    });
  }
  return globalForSocket.__coreGuardSocket;
}

export type AgentLog = {
  timestamp: string;
  agent: string;
  message: string;
  type: "info" | "warning" | "success" | "error";
};
