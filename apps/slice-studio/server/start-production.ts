import { existsSync } from "node:fs";

const processes: Bun.Subprocess[] = [];
const standaloneServerPath = resolveStandaloneServerPath();

start("api", ["bun", "server/index.ts"], {
  SLICE_STUDIO_API_HOST: process.env.SLICE_STUDIO_API_HOST || "0.0.0.0",
  SLICE_STUDIO_API_PORT: process.env.SLICE_STUDIO_API_PORT || "4110",
  SLICE_STUDIO_ALLOWED_ORIGIN: process.env.SLICE_STUDIO_ALLOWED_ORIGIN || "http://127.0.0.1:3010"
});

start("web", ["bun", standaloneServerPath], {
  HOSTNAME: "0.0.0.0",
  PORT: process.env.SLICE_STUDIO_WEB_PORT || "3010"
});

for (const signal of ["SIGINT", "SIGTERM"] as const) {
  process.on(signal, () => {
    shutdown(signal);
  });
}

await Promise.race(processes.map((child) => child.exited));
shutdown("child_exit");

function start(name: string, cmd: string[], env: Record<string, string> = {}): void {
  const child = Bun.spawn(cmd, {
    env: { ...process.env, ...env },
    stdout: "inherit",
    stderr: "inherit"
  });
  processes.push(child);
  console.log(`[slice-studio] started ${name} pid=${child.pid}`);
}

function resolveStandaloneServerPath(): string {
  const candidates = [
    ".next/standalone/apps/slice-studio/server.js",
    ".next/standalone/server.js"
  ];
  for (const candidate of candidates) {
    if (existsSync(candidate)) {
      return candidate;
    }
  }
  throw new Error(`Next standalone server not found in: ${candidates.join(", ")}`);
}

function shutdown(reason: string): never {
  console.log(`[slice-studio] shutting down: ${reason}`);
  for (const child of processes) {
    child.kill();
  }
  process.exit(reason === "child_exit" ? 1 : 0);
}

export {};
