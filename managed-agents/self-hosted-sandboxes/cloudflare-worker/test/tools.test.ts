import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { fakeTools, type FakeFS } from "../src/tools.ts";

async function call(fs: FakeFS, name: string, input: Record<string, unknown>): Promise<string> {
  const tool = fakeTools(fs).find((item) => item.name === name);
  assert.ok(tool, name);
  const result = await tool.run(input as never);
  assert.equal(typeof result, "string");
  return result;
}

describe("glob", () => {
  const fs: FakeFS = new Map([
    ["a.ts", "export const a = 1;\n"],
    ["src/a.ts", "export const a = 1;\n"],
    ["src/sub/a.ts", "export const nested = 1;\n"],
    ["src/a.js", "export const js = 1;\n"],
    ["other/a.ts", "export const other = 1;\n"],
    ["price$.ts", "export const dollars = 1;\n"],
  ]);

  it("matches root and nested files for **/*.ts", async () => {
    const hits = (await call(fs, "glob", { pattern: "**/*.ts" })).split("\n");
    assert.deepEqual(hits, ["a.ts", "other/a.ts", "price$.ts", "src/a.ts", "src/sub/a.ts"]);
  });

  it("keeps a directory prefix on **", async () => {
    const hits = (await call(fs, "glob", { pattern: "src/**/*.ts" })).split("\n");
    assert.deepEqual(hits, ["src/a.ts", "src/sub/a.ts"]);
  });

  it("does not let a single star cross a slash", async () => {
    assert.equal(await call(fs, "glob", { pattern: "*.ts" }), "a.ts\nprice$.ts");
  });

  it("treats $ in a path as a literal when grep scopes with a glob", async () => {
    assert.equal(
      await call(fs, "grep", { pattern: "dollars", path: "price$.ts" }),
      "price$.ts:1:export const dollars = 1;",
    );
  });
});

describe("edit", () => {
  it("stores dollar replacement patterns as literal text", async () => {
    const fs: FakeFS = new Map([["price.txt", "const price = 1;\n"]]);
    assert.equal(
      await call(fs, "edit", { file_path: "price.txt", old_string: "1", new_string: "$&$&" }),
      "edited price.txt",
    );
    assert.equal(fs.get("price.txt"), "const price = $&$&;\n");
  });

  it("replaces only the first match", async () => {
    const fs: FakeFS = new Map([["n.txt", "1 1"]]);
    await call(fs, "edit", { file_path: "n.txt", old_string: "1", new_string: "2" });
    assert.equal(fs.get("n.txt"), "2 1");
  });

  it("reports a missing old_string without writing", async () => {
    const fs: FakeFS = new Map([["n.txt", "hello"]]);
    assert.equal(
      await call(fs, "edit", { file_path: "n.txt", old_string: "missing", new_string: "$&" }),
      "error: old_string not found in n.txt",
    );
    assert.equal(fs.get("n.txt"), "hello");
  });
});
