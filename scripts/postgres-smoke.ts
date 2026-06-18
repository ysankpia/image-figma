process.env.SLICE_STUDIO_LOAD_LOCAL_ENV = "false";
process.env.SLICE_STUDIO_DATABASE_PROVIDER = "postgres";
process.env.SLICE_STUDIO_STORAGE_ROOT = process.env.SLICE_STUDIO_STORAGE_ROOT || "/tmp/slice-studio-postgres-smoke";
process.env.SLICE_STUDIO_LOCAL_OWNER_EMAIL = process.env.SLICE_STUDIO_LOCAL_OWNER_EMAIL || "owner@example.test";
process.env.SLICE_STUDIO_LOCAL_OWNER_NAME = process.env.SLICE_STUDIO_LOCAL_OWNER_NAME || "Owner";
process.env.SLICE_STUDIO_LOCAL_OWNER_PASSWORD = process.env.SLICE_STUDIO_LOCAL_OWNER_PASSWORD || "owner-password";

if (!process.env.SLICE_STUDIO_DATABASE_URL) {
  throw new Error("SLICE_STUDIO_DATABASE_URL is required for postgres smoke");
}

const dbModule = await import("../server/db");
const auth = await import("../server/auth");
const projects = await import("../server/projects");

try {
  await dbModule.initDatabase();
  await resetUserOnlyTables();
  await dbModule.initDatabase();
  const owner = await auth.ensureLocalOwner();
  const project = await projects.createProject(owner.id, { name: "postgres-smoke-project" });
  const listed = await projects.listProjectCards(owner.id);
  if (!listed.some((item) => item.id === project.id)) throw new Error("created project missing from list");
  await projects.deleteProject(owner.id, project.id);
  const afterDelete = await projects.listProjectCards(owner.id);
  if (afterDelete.some((item) => item.id === project.id)) throw new Error("deleted project still listed");
  console.log(JSON.stringify({ ok: true, provider: dbModule.db.provider, owner: owner.email }));
} finally {
  await dbModule.db.close();
}

async function resetUserOnlyTables(): Promise<void> {
  await dbModule.db.exec(`
    DROP TABLE IF EXISTS slices;
    DROP TABLE IF EXISTS pages;
    DROP TABLE IF EXISTS projects;
    DROP TABLE IF EXISTS sessions;
    DROP TABLE IF EXISTS users;
    DROP TABLE IF EXISTS schema_migrations;
    DROP TABLE IF EXISTS payment_events;
    DROP TABLE IF EXISTS payment_orders;
    DROP TABLE IF EXISTS entitlements;
    DROP TABLE IF EXISTS plans;
    DROP TABLE IF EXISTS usage_events;
  `);
}

export {};
