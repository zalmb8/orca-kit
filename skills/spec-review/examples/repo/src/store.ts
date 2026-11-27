import { readFileSync, renameSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import type { Todo } from "./types";

export const STORE_PATH = process.env.TODO_STORE ?? join(homedir(), ".todos.json");

// Reads every todo in one call. Throws if the store can't be read or parsed.
// A missing store file is an empty store.
export function loadTodos(path: string = STORE_PATH): Todo[] {
  let text: string;
  try {
    text = readFileSync(path, "utf8");
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code === "ENOENT") return [];
    throw e;
  }
  return JSON.parse(text) as Todo[];
}

// Writes every todo atomically: a temp file next to the store, renamed over it
// (docs/adr/0001-store-access.md).
export function saveTodos(todos: Todo[], path: string = STORE_PATH): void {
  const tmp = join(dirname(path), `.todos.${process.pid}.tmp`);
  writeFileSync(tmp, JSON.stringify(todos, null, 2) + "\n", "utf8");
  renameSync(tmp, path);
}
