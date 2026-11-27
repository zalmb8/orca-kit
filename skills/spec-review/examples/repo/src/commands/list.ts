import { loadTodos } from "../store";

// Prints one line per todo, in store order. The format is documented in
// docs/list-output.md.
export function list(args: string[]): number {
  if (args.length > 0) {
    process.stderr.write("usage: todo list\n");
    return 2;
  }
  for (const todo of loadTodos()) {
    process.stdout.write(`- [${todo.done ? "x" : " "}] ${todo.title}\n`);
  }
  return 0;
}
