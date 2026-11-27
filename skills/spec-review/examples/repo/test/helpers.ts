import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import type { Todo } from "../src/types";

// Runs fn with TODO_STORE pointing at a temp store holding todos.
export function withStore(todos: Todo[], fn: (path: string) => void): void {
  const dir = mkdtempSync(join(tmpdir(), "todo-"));
  const path = join(dir, "todos.json");
  writeFileSync(path, JSON.stringify(todos));
  process.env.TODO_STORE = path;
  try {
    fn(path);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

export function runCli(args: string[]): { status: number; stdout: string; stderr: string } {
  const r = spawnSync("node", ["dist/cli.js", ...args], { encoding: "utf8", env: process.env });
  return { status: r.status ?? -1, stdout: r.stdout, stderr: r.stderr };
}
