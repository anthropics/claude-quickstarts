import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { findLiveSandbox, processWorkItem } from "../api/webhook.ts";

const sessionId = "sesn_abc";

function memoryKv() {
  const data = new Map<string, string>();
  return {
    data,
    async get<T>(key: string): Promise<T | null> {
      return (data.get(key) as T | undefined) ?? null;
    },
    async set(key: string, value: unknown): Promise<void> {
      data.set(key, String(value));
    },
    async del(key: string): Promise<void> {
      data.delete(key);
    },
  };
}

function client() {
  return {
    beta: {
      environments: {
        work: {
          ack: async () => undefined,
          stop: async () => undefined,
        },
      },
    },
  };
}

function work() {
  return { id: "work_abc", secret: "session-secret", data: { id: sessionId } };
}

describe("failed sandbox setup", () => {
  it("does not keep a mapping or a running VM when npm install fails", async () => {
    const kv = memoryKv();
    const events: string[] = [];
    const createSandbox = async () => ({
      sandboxId: "sb_bad",
      writeFiles: async () => undefined,
      stop: async () => {
        events.push("stop");
      },
      runCommand: async (opts: { args?: string[] }) => {
        const line = (opts.args ?? []).join(" ");
        if (line.includes("npm install")) {
          return { exitCode: 1, output: async () => "registry down" };
        }
        return { exitCode: 0, output: async () => "" };
      },
    });

    await assert.rejects(
      () =>
        processWorkItem(client() as never, work(), "env_abc", "env-key", {
          createSandbox: createSandbox as never,
          kv,
        }),
      /npm install failed/,
    );
    assert.equal(kv.data.size, 0);
    assert.deepEqual(events, ["stop"]);
  });

  it("records the mapping once the runner has started", async () => {
    const kv = memoryKv();
    const events: string[] = [];
    const createSandbox = async () => ({
      sandboxId: "sb_ok",
      writeFiles: async () => undefined,
      stop: async () => {
        events.push("stop");
      },
      runCommand: async (opts: { cmd: string; args?: string[] }) => {
        const line = `${opts.cmd} ${(opts.args ?? []).join(" ")}`;
        if (line.includes("npm install")) return { exitCode: 0, output: async () => "" };
        if (opts.cmd === "node") {
          return {
            logs: async function* () {
              yield { data: "ready\n" };
            },
          };
        }
        return { exitCode: 0, output: async () => "" };
      },
    });

    const result = await processWorkItem(client() as never, work(), "env_abc", "env-key", {
      createSandbox: createSandbox as never,
      kv,
    });
    assert.equal(result.sandbox_id, "sb_ok");
    assert.equal(kv.data.get(`shs:sandbox:${sessionId}`), "sb_ok");
    assert.deepEqual(events, []);
  });
});

describe("runner that has exited", () => {
  it("drops the mapping and stops the VM instead of extending it", async () => {
    const kv = memoryKv();
    await kv.set(`shs:sandbox:${sessionId}`, "sb_dead");
    const events: string[] = [];
    const sandbox = {
      sandboxId: "sb_dead",
      status: "running",
      stop: async () => {
        events.push("stop");
      },
      extendTimeout: async () => {
        events.push("extend");
      },
      runCommand: async (opts: { args?: string[] }) => {
        const line = (opts.args ?? []).join(" ");
        if (line.includes("pgrep")) return { exitCode: 1, output: async () => "" };
        return { exitCode: 0, output: async () => "" };
      },
    };

    const found = await findLiveSandbox(sessionId, {
      kv,
      getSandbox: async () => sandbox as never,
    });
    assert.equal(found, null);
    assert.equal(kv.data.size, 0);
    assert.deepEqual(events, ["stop"]);
  });
});
