import { loadTodos, saveTodos } from "../store";

export function add(args: string[]): number {
  const title = args.join(" ").trim();
  if (title === "") {
    process.stderr.write("usage: todo add <title>\n");
    return 2;
  }
  const todos = loadTodos();
  const id = todos.reduce((max, t) => Math.max(max, t.id), 0) + 1;
  todos.push({ id, title, done: false, createdAt: new Date().toISOString(), due: null, link: null });
  saveTodos(todos);
  process.stdout.write(`added ${id}\n`);
  return 0;
}
