import fs from "node:fs";

const filePath = process.argv[2];

if (!filePath) {
  console.error("Usage: node tools/scan-bundle.mjs <bundle-file>");
  process.exit(1);
}

const source = fs.readFileSync(filePath, "utf8");
const checks = [
  { name: "top-level import/export", pattern: /^\s*(import|export)\s/m },
  { name: "structuredClone", pattern: /\bstructuredClone\s*\(/ },
  { name: "Object.hasOwn", pattern: /\bObject\.hasOwn\s*\(/ },
  { name: "for await", pattern: /\bfor\s+await\b/ }
];

const failures = checks.filter((check) => check.pattern.test(source));

if (failures.length > 0) {
  console.error(`Figma bundle compatibility scan failed for ${filePath}:`);
  for (const failure of failures) {
    console.error(`- ${failure.name}`);
  }
  process.exit(1);
}

console.log(`Figma bundle compatibility scan passed: ${filePath}`);
