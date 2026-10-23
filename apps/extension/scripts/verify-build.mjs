import { readFile } from "node:fs/promises";

const files = ["dist/content.js", "dist/service-worker.js"];
for (const file of files) {
  const source = await readFile(new URL(`../${file}`, import.meta.url), "utf8");
  if (source.includes("process.env") || source.includes("process is not defined")) {
    throw new Error(`${file} contains a Node-only process reference`);
  }
}

console.log("Extension runtime bundles contain no Node-only process references.");
