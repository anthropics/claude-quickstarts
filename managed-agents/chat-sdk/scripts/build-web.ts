// Deploy build step, shared by every platform config (vercel.json,
// netlify.toml, wrangler.jsonc): prebuild the chat page into public/ so the
// deployed handler never reads files or runs esbuild at request time.
// Locally, src/main.ts still bundles on request -- this script is deploy-only.
// The bundle recipe itself lives in src/bundle.ts, shared with the dev
// server so the two can't drift.

import { copyFile, mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import * as esbuild from "esbuild";
import { webBundleOptions, webFile } from "../src/bundle";

const outDir = fileURLToPath(new URL("../public", import.meta.url));

await mkdir(outDir, { recursive: true });

await esbuild.build({
  ...webBundleOptions("production"),
  outfile: `${outDir}/app.js`,
});

await copyFile(webFile("index.html"), `${outDir}/index.html`);
await copyFile(webFile("app.css"), `${outDir}/app.css`);

console.log("built public/: index.html, app.css, app.js");
