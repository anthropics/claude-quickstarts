/**
 * In-isolate "fake sandbox" tools for the pure-Worker variant.
 *
 * Backed by a Map<string,string> held in the Durable Object: no real shell or
 * filesystem. Demonstrates passing custom tools to
 * client.beta.sessions.events.toolRunner (same shape as
 * client.beta.messages.toolRunner accepts).
 */
import { betaZodTool } from "@anthropic-ai/sdk/helpers/beta/zod";
import { z } from "zod";

export type FakeFS = Map<string, string>;

// `glob` and `grep` compile a RegExp from text the model wrote, and the model
// reads untrusted content. Bound the pattern and the output so a hostile
// pattern costs bounded CPU. The Workers CPU limit is the backstop.
const MAX_PATTERN_CHARS = 256;
const MAX_MATCHES = 500;

function compile(pattern: string): RegExp | string {
  if (pattern.length > MAX_PATTERN_CHARS) return `error: pattern is longer than ${MAX_PATTERN_CHARS} characters`;
  try {
    return new RegExp(pattern);
  } catch {
    return "error: pattern is not a valid regular expression";
  }
}

function globToRegex(pat: string): RegExp {
  const esc = pat.replace(/[.+^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`^${esc.replace(/\*\*/g, ".*").replace(/\*/g, "[^/]*").replace(/\?/g, "[^/]")}$`);
}

export function fakeTools(fs: FakeFS) {
  const read = betaZodTool({
    name: "read",
    description: "Read a file from the in-memory workspace.",
    inputSchema: z.object({ file_path: z.string() }),
    run: ({ file_path }) => fs.get(file_path) ?? `error: ${file_path}: no such file`,
  });

  const write = betaZodTool({
    name: "write",
    description: "Write a file to the in-memory workspace.",
    inputSchema: z.object({ file_path: z.string(), content: z.string() }),
    run: ({ file_path, content }) => {
      fs.set(file_path, content);
      return `wrote ${content.length} bytes to ${file_path}`;
    },
  });

  const edit = betaZodTool({
    name: "edit",
    description: "Replace the first occurrence of old_string with new_string.",
    inputSchema: z.object({ file_path: z.string(), old_string: z.string(), new_string: z.string() }),
    run: ({ file_path, old_string, new_string }) => {
      const cur = fs.get(file_path);
      if (cur === undefined) return `error: ${file_path}: no such file`;
      if (!cur.includes(old_string)) return `error: old_string not found in ${file_path}`;
      fs.set(file_path, cur.replace(old_string, new_string));
      return `edited ${file_path}`;
    },
  });

  const glob = betaZodTool({
    name: "glob",
    description: "List workspace paths matching a glob pattern.",
    inputSchema: z.object({ pattern: z.string() }),
    run: ({ pattern }) => {
      if (pattern.length > MAX_PATTERN_CHARS) return `error: pattern is longer than ${MAX_PATTERN_CHARS} characters`;
      const re = globToRegex(pattern);
      const hits = [...fs.keys()].filter((p) => re.test(p)).sort().slice(0, MAX_MATCHES);
      return hits.length ? hits.join("\n") : "(no matches)";
    },
  });

  const grep = betaZodTool({
    name: "grep",
    description: "Search workspace files for a regex; returns path:line:text.",
    inputSchema: z.object({ pattern: z.string(), path: z.string().optional() }),
    run: ({ pattern, path }) => {
      const re = compile(pattern);
      if (typeof re === "string") return re;
      if (path !== undefined && path.length > MAX_PATTERN_CHARS) {
        return `error: path is longer than ${MAX_PATTERN_CHARS} characters`;
      }
      const scope = path ? globToRegex(path) : /.*/;
      const out: string[] = [];
      for (const [p, content] of fs) {
        if (!scope.test(p)) continue;
        const lines = content.split("\n");
        for (let i = 0; i < lines.length && out.length < MAX_MATCHES; i++) {
          if (re.test(lines[i]!)) out.push(`${p}:${i + 1}:${lines[i]}`);
        }
        if (out.length >= MAX_MATCHES) break;
      }
      return out.length ? out.join("\n") : "(no matches)";
    },
  });

  const bash = betaZodTool({
    name: "bash",
    description: "Not available in the Worker isolate.",
    inputSchema: z.object({ command: z.string() }),
    run: () =>
      "error: bash is not available in this environment. Use read, write, edit, glob, and grep instead.",
  });

  return [bash, read, write, edit, glob, grep];
}
