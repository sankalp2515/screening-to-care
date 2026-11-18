// Copies the recorded synthetic demo bundle into public/ so demo mode works offline.
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, "../demo/demo-bundle.json");
const dest = resolve(here, "../public/demo-bundle.json");
if (!existsSync(src)) { console.error("demo bundle not found at " + src); process.exit(1); }
mkdirSync(dirname(dest), { recursive: true });
copyFileSync(src, dest);
console.log("demo bundle synced");
