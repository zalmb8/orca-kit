import { describe, expect, it } from "vitest";
import { runCli, withStore } from "../helpers";

describe("todo list", () => {
  it("prints one line per todo", () => {
    withStore([{ id: 1, title: "Buy milk", done: false, createdAt: "2026-11-01T09:00:00Z", due: null, link: null }], () => {
      expect(runCli(["list"]).stdout).toBe("- [ ] Buy milk\n");
    });
  });
});
