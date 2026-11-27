#!/usr/bin/env node
import { add } from "./commands/add";
import { done } from "./commands/done";
import { list } from "./commands/list";

const commands: Record<string, (args: string[]) => number> = { add, done, list };

function usage(): number {
  process.stderr.write("usage: todo <add|done|list> [args]\n");
  return 2;
}

export function main(argv: string[]): number {
  const [name, ...args] = argv;
  const command = name === undefined ? undefined : commands[name];
  if (!command) return usage();
  try {
    return command(args);
  } catch (e) {
    process.stderr.write(`todo: ${(e as Error).message}\n`);
    return 1;
  }
}

process.exitCode = main(process.argv.slice(2));
