// Posts the user's open todos to the team's standup channel each morning.
// Runs `todo list` and parses its output (docs/list-output.md).
import { execFileSync } from "node:child_process";

const LINE = /^- \[( |x)\] (.+)$/;

export function openTitles(listOutput: string): string[] {
  return listOutput
    .split("\n")
    .map((line) => LINE.exec(line))
    .filter((m): m is RegExpExecArray => m !== null && m[1] === " ")
    .map((m) => m[2]);
}

export async function postDigest(webhookUrl: string): Promise<void> {
  const titles = openTitles(execFileSync("todo", ["list"], { encoding: "utf8" }));
  await fetch(webhookUrl, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ text: titles.map((t) => `• ${t}`).join("\n") }),
  });
}
