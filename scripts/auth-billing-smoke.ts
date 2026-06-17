import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const root = fs.mkdtempSync(path.join(os.tmpdir(), "slice-studio-auth-billing-"));

process.env.SLICE_STUDIO_LOAD_LOCAL_ENV = "false";
process.env.SLICE_STUDIO_STORAGE_ROOT = root;
process.env.SLICE_STUDIO_LOCAL_OWNER_EMAIL = "owner@example.test";
process.env.SLICE_STUDIO_LOCAL_OWNER_NAME = "Owner";
process.env.SLICE_STUDIO_LOCAL_OWNER_PASSWORD = "owner-password";
process.env.SLICE_STUDIO_FREE_PROJECT_LIMIT = "1";
process.env.SLICE_STUDIO_MAX_PAGES_PER_PROJECT = "1";
process.env.SLICE_STUDIO_XPAY_BASE_URL = "https://pay.example.test";
process.env.SLICE_STUDIO_XPAY_PID = "1000";
process.env.SLICE_STUDIO_XPAY_KEY = "xpay-test-key";
process.env.SLICE_STUDIO_XPAY_NOTIFY_URL = "https://slice.example.test/api/billing/webhooks/xpay";
process.env.SLICE_STUDIO_XPAY_RETURN_URL = "https://slice.example.test/billing";
process.env.SLICE_STUDIO_ALLOW_XPAY_TEST_SIGN = "true";

try {
  const dbModule = await import("../server/db");
  dbModule.initDatabase();
  const auth = await import("../server/auth");
  const billing = await import("../server/billing");
  const projects = await import("../server/projects");
  const xpay = await import("../server/xpay");

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
  const quotaProject = projects.createProject(bob.id, { name: "Quota project" });
  assertThrows(() => projects.createProject(bob.id, { name: "Second project" }), "Project quota exhausted");
  dbModule.db.query("UPDATE entitlements SET storage_mb = 0 WHERE user_id = ?").run(bob.id);
  await assertRejects(
    () => projects.addPages(bob.id, quotaProject.id, [makeUpload("quota.png")]),
    "Storage quota exhausted"
  );
  dbModule.db.query("UPDATE entitlements SET status = 'active' WHERE user_id = ?").run(alice.id);
  const singlePageProject = projects.createProject(alice.id, { name: "Page quota project" });
  await assertRejects(
    () => projects.addPages(alice.id, singlePageProject.id, [makeUpload("p1.png"), makeUpload("p2.png")]),
    "Project page quota exhausted"
  );

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
  assert(order.checkoutUrl?.startsWith("https://pay.example.test/submit.php?"), "configured XPay order should include checkout URL");
  assert(billing.listPaymentOrders(alice.id)[0]?.id === order.id, "payment order should be stored");
  const failedWebhook = billing.handlePaymentWebhook({
    provider: "xpay",
    body: {
      pid: "1000",
      trade_no: "provider_bad",
      out_trade_no: order.id,
      type: "alipay",
      name: "Pro",
      money: "99.00",
      trade_status: "TRADE_SUCCESS",
      sign: "bad-sign",
      sign_type: "MD5"
    }
  });
  assert(!failedWebhook.accepted, "bad XPay signature should not be accepted");
  assert(billing.getEntitlementSummary(alice.id).plan.id === "free", "bad XPay signature should not grant entitlement");
  const notify = {
    pid: "1000",
    trade_no: "provider_123",
    out_trade_no: order.id,
    type: "alipay",
    name: "Pro",
    money: "99.00",
    trade_status: "TRADE_SUCCESS",
    sign: "",
    sign_type: "MD5"
  };
  notify.sign = xpay.signXPayForTest(notify);
  const paidWebhook = billing.handlePaymentWebhook({ provider: "xpay", body: notify });
  assert(paidWebhook.accepted && paidWebhook.status === "paid", "valid XPay success webhook should mark order paid");
  assert(billing.getEntitlementSummary(alice.id).plan.id === "pro", "valid XPay success webhook should grant paid plan");
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

async function assertRejects(fn: () => Promise<unknown>, message: string): Promise<void> {
  try {
    await fn();
  } catch (error) {
    if (error instanceof Error && error.message.includes(message)) return;
    throw error;
  }
  throw new Error(`Expected error: ${message}`);
}

function makeUpload(name: string): File {
  return new File([arrayBufferFromBytes(createTinyPng())], name, { type: "image/png" });
}

function createTinyPng(): Uint8Array {
  return Uint8Array.from(Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAAAI0lEQVR42mP8z8Dwn4GKgImaho0aNmjYoGGDho0bFAAAoO0CH2pX1EAAAAAASUVORK5CYII=",
    "base64"
  ));
}

function arrayBufferFromBytes(bytes: Uint8Array): ArrayBuffer {
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer;
}
