import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const root = fs.mkdtempSync(path.join(os.tmpdir(), "slice-studio-auth-billing-"));

process.env.SLICE_STUDIO_LOAD_LOCAL_ENV = "false";
process.env.SLICE_STUDIO_STORAGE_ROOT = root;
process.env.SLICE_STUDIO_LOCAL_OWNER_EMAIL = "owner@example.test";
process.env.SLICE_STUDIO_LOCAL_OWNER_NAME = "Owner";
process.env.SLICE_STUDIO_LOCAL_OWNER_PASSWORD = "owner-password";

try {
  const dbModule = await import("../server/db");
  dbModule.initDatabase();
  const auth = await import("../server/auth");
  const billing = await import("../server/billing");
  const projects = await import("../server/projects");

  const owner = auth.ensureLocalOwner();
  auth.seedEntitlement(owner.id);
  assert(owner.role === "admin", "local owner should be admin");
  dbModule.db.query("UPDATE users SET password_hash = ? WHERE id = ?").run(auth.hashPassword("wrong-password"), owner.id);
  const refreshedOwner = auth.ensureLocalOwner();
  const signedIn = auth.signInWithEmail("owner@example.test", "owner-password");
  assert(signedIn.user.id === refreshedOwner.id, "local owner password should be repeatable");

  const cookie = auth.buildSessionCookie(signedIn.token, signedIn.expiresAt);
  const currentUser = auth.getCurrentUser(new Request("http://slice.test", { headers: { cookie } }));
  assert(currentUser?.id === refreshedOwner.id, "session cookie should resolve current user");

  const alice = auth.signUpWithEmail("Alice", "alice@example.test", "password-123").user;
  const bob = auth.signUpWithEmail("Bob", "bob@example.test", "password-123").user;
  const project = projects.createProject(alice.id, { name: "Alice project" });
  assert(projects.listProjectCards(alice.id).some((item) => item.id === project.id), "owner should list own project");
  assert(projects.listProjectCards(bob.id).length === 0, "other user should not list owner project");
  assertThrows(() => projects.getProjectDetail(bob.id, project.id), "Project not found");

  const before = billing.getEntitlementSummary(alice.id).entitlement;
  billing.consumeAiCall(alice.id, project.id, { pageId: "page_0001" });
  billing.consumeExport(alice.id, project.id, "export.assets", { assetCount: 2 });
  const after = billing.getEntitlementSummary(alice.id).entitlement;
  assert(after.ai_calls_remaining === before.ai_calls_remaining - 1, "AI quota should decrease");
  assert(after.exports_remaining === before.exports_remaining - 1, "export quota should decrease");
  const usageTypes = billing.listUsageEvents(alice.id).map((event) => event.event_type);
  assert(usageTypes.includes("export.assets") && usageTypes.includes("ai.boxes"), "usage events should be written");

  const order = billing.createPaymentOrder(alice.id, "pro", "xpay");
  assert(order.provider === "xpay" && order.status === "pending", "XPay reserved order should be pending");
  assert(billing.listPaymentOrders(alice.id)[0]?.id === order.id, "payment order should be stored");
  assert(billing.getAdminOverview().users >= 3, "admin overview should count users");

  console.log("auth-billing smoke passed");
  dbModule.db.close(false);
} finally {
  fs.rmSync(root, { recursive: true, force: true });
}

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

function assertThrows(fn: () => unknown, message: string): void {
  try {
    fn();
  } catch (error) {
    if (error instanceof Error && error.message.includes(message)) return;
    throw error;
  }
  throw new Error(`Expected error: ${message}`);
}
