import sharp from "sharp";
import { mkdir, readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const svg = await readFile(new URL("../src/assets/logo.svg", import.meta.url));
const output = new URL("../dist/icons/", import.meta.url);
await mkdir(output, { recursive: true });
for (const size of [16, 32, 48, 128]) {
  const path = fileURLToPath(new URL(`icon-${size}.png`, output));
  await sharp(svg).resize(size, size).png().toFile(path);
}
