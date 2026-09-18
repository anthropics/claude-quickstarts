#!/usr/bin/env bun
// stdio transport, for Claude Desktop and Claude Code.
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { registerTools } from "./tools";

const server = new McpServer({ name: "managed-agents-mcp", version: "0.1.0" });
registerTools(server);

await server.connect(new StdioServerTransport());
// stdout carries the protocol, so logs go to stderr.
console.error("[managed-agents-mcp] stdio server ready");
