import { loadTodos, saveTodos } from "../store";

export function done(args: string[]): number {
  const id = Number(args[0]);
  if (args.length !== 1 || !Number.isInteger(id)) {
    process.stderr.write("usage: todo done <id>\n");
    return 2;
  }
  const todos = loadTodos();
  const todo = todos.find((t) => t.id === id);
  if (!todo) {
    process.stderr.write(`todo: no todo ${id}\n`);
    return 1;
  }
  todo.done = true;
  saveTodos(todos);
  return 0;
}
