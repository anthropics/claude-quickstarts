// One esbuild recipe for the chat page, shared by the dev server
// (src/main.ts bundles on request) and the deploy build
// (scripts/build-web.ts writes public/). Sharing it here is what keeps the
// deployed bundle byte-compatible with what dev served: a loader or define
// added for a new web dependency lands in both paths or neither.

import { fileURLToPath } from "node:url";
import type * as esbuild from "esbuild";

export const webFile = (name: string) => fileURLToPath(new URL(`../web/${name}`, import.meta.url));

export function webBundleOptions(nodeEnv: string): esbuild.BuildOptions {
  const production = nodeEnv === "production";
  return {
    entryPoints: [webFile("app.tsx")],
    bundle: true,
    format: "esm",
    // The sourcemap is most of the bundle's weight; production drops it.
    sourcemap: production ? false : "inline",
    minify: production,
    // React's entry points branch on this at require time; without the
    // define, the browser bundle would reference a `process` that isn't there.
    define: { "process.env.NODE_ENV": JSON.stringify(nodeEnv) },
  };
}
