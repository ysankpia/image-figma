import { describe, expect, it } from "vitest";
import { schemaMigrations } from "../server/db-migrations";

describe("schema migrations metadata", () => {
  it("keeps migration ids ordered and unique", () => {
    const ids = schemaMigrations.map((migration) => migration.id);
    expect(ids).toEqual([...ids].sort());
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("documents the current DB repair stages explicitly", () => {
    expect(schemaMigrations.map((migration) => migration.id)).toEqual([
      "001_base_current_schema",
      "002_projects_user_ownership",
      "003_auth_profile_columns",
      "004_usage_events_contract",
      "005_payment_events_contract",
      "006_pages_and_slices_contract",
      "007_seed_default_plans"
    ]);
  });
});
