import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import Ajv from "ajv";
import type { DesignDSL } from "../src";

const currentDir = dirname(fileURLToPath(import.meta.url));
const packageRoot = join(currentDir, "..");

export function loadExample(name: string): DesignDSL {
  return JSON.parse(readFileSync(join(packageRoot, "examples", name), "utf8")) as DesignDSL;
}

export function loadSchema(): object {
  return JSON.parse(readFileSync(join(packageRoot, "schemas", "dsl-v0.1.schema.json"), "utf8")) as object;
}

export function createSchemaValidator() {
  const ajv = new Ajv({ allErrors: true });
  return ajv.compile(loadSchema());
}
