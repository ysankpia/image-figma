const { spawnSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const rootDir = path.resolve(__dirname, "..");
const htmlPath = path.join(rootDir, "manual-slice.html");
const html = fs.readFileSync(htmlPath, "utf8");
const scripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)].map((match) => match[1]);

if (!scripts.length) {
  throw new Error("manual-slice.html does not contain an inline script");
}

const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "manual-slice-check-"));
const tempFile = path.join(tempDir, "manual-slice.inline.js");

try {
  fs.writeFileSync(tempFile, scripts.join("\n\n"), "utf8");
  const result = spawnSync(process.execPath, ["--check", tempFile], { stdio: "inherit" });
  if (result.status !== 0) {
    process.exit(result.status || 1);
  }
} finally {
  fs.rmSync(tempDir, { recursive: true, force: true });
}
