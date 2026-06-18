import crypto from "node:crypto";
import { authCookieName, authSecureCookies, authSessionTtlDays, localOwnerEmail, localOwnerName, localOwnerPassword } from "./config";
import { db, type SessionRow, type UserRow } from "./db";
import { httpError } from "./errors";
import { randomHex } from "./utils";

export type CurrentUser = {
  id: string;
  email: string;
  name: string;
  role: "user" | "admin";
  status: "active" | "suspended";
};

export async function ensureLocalOwner(): Promise<CurrentUser> {
  const existing = await getUserByEmail(localOwnerEmail);
  const now = new Date().toISOString();
  const passwordHash = hashPassword(localOwnerPassword);
  if (existing) {
    await db.run(`
      UPDATE users
      SET name = ?, password_hash = ?, role = 'admin', status = 'active', updated_at = ?
      WHERE id = ?
    `, [localOwnerName, passwordHash, now, existing.id]);
    const refreshed = await getUserByEmail(localOwnerEmail);
    if (!refreshed) throw httpError(500, "Local owner refresh failed");
    return formatUser(refreshed);
  }
  const id = `user_${randomHex(8)}`;
  await db.run(`
    INSERT INTO users (id, email, name, password_hash, role, status, created_at, updated_at)
    VALUES (?, ?, ?, ?, 'admin', 'active', ?, ?)
  `, [id, localOwnerEmail, localOwnerName, passwordHash, now, now]);
  return { id, email: localOwnerEmail, name: localOwnerName, role: "admin", status: "active" };
}

export async function createSession(userId: string): Promise<{ token: string; expiresAt: string }> {
  const now = new Date();
  const expiresAt = new Date(now.getTime() + authSessionTtlDays * 24 * 60 * 60 * 1000);
  const token = randomHex(32);
  const tokenHash = hashToken(token);
  const id = `session_${randomHex(8)}`;
  await db.run(`
    INSERT INTO sessions (id, user_id, token_hash, expires_at, created_at, last_seen_at)
    VALUES (?, ?, ?, ?, ?, ?)
  `, [id, userId, tokenHash, expiresAt.toISOString(), now.toISOString(), now.toISOString()]);
  return { token, expiresAt: expiresAt.toISOString() };
}

export async function getCurrentUser(request: globalThis.Request): Promise<CurrentUser | null> {
  const token = readSessionToken(request);
  if (!token) return null;
  const session = await getSessionByToken(token);
  if (!session) return null;
  if (Date.parse(session.expires_at) <= Date.now()) {
    await db.run("DELETE FROM sessions WHERE id = ?", [session.id]);
    return null;
  }
  const user = await getUserById(session.user_id);
  if (!user) return null;
  if (user.status !== "active") return null;
  await db.run("UPDATE sessions SET last_seen_at = ? WHERE id = ?", [new Date().toISOString(), session.id]);
  return formatUser(user);
}

export async function requireUser(request: globalThis.Request): Promise<CurrentUser> {
  const user = await getCurrentUser(request);
  if (!user) throw httpError(401, "Authentication required");
  return user;
}

export function readSessionToken(request: globalThis.Request): string | null {
  const cookie = request.headers.get("cookie") || "";
  const token = cookie.split(";").map((part: string) => part.trim()).find((part: string) => part.startsWith(`${authCookieName}=`))?.slice(authCookieName.length + 1);
  return token ? decodeURIComponent(token) : null;
}

export function buildSessionCookie(token: string, expiresAt: string): string {
  const parts = [
    `${authCookieName}=${encodeURIComponent(token)}`,
    "Path=/",
    "HttpOnly",
    "SameSite=Lax",
    `Expires=${new Date(expiresAt).toUTCString()}`
  ];
  if (authSecureCookies) parts.push("Secure");
  return parts.join("; ");
}

export function clearSessionCookie(): string {
  const parts = [
    `${authCookieName}=`,
    "Path=/",
    "HttpOnly",
    "SameSite=Lax",
    "Max-Age=0"
  ];
  if (authSecureCookies) parts.push("Secure");
  return parts.join("; ");
}

export async function signInWithEmail(email: string, password: string): Promise<{ user: CurrentUser; token: string; expiresAt: string }> {
  const normalizedEmail = normalizeEmail(email);
  const user = await getUserByEmail(normalizedEmail);
  if (!user || !verifyPassword(password, user.password_hash)) {
    throw httpError(401, "Invalid email or password");
  }
  if (user.status !== "active") throw httpError(403, "Account is suspended");
  const session = await createSession(user.id);
  return { user: formatUser(user), token: session.token, expiresAt: session.expiresAt };
}

export async function signUpWithEmail(name: string, email: string, password: string): Promise<{ user: CurrentUser; token: string; expiresAt: string }> {
  const normalizedEmail = normalizeEmail(email);
  if (await getUserByEmail(normalizedEmail)) throw httpError(409, "Email already exists");
  const now = new Date().toISOString();
  const id = `user_${randomHex(8)}`;
  const passwordHash = hashPassword(password);
  await db.run(`
    INSERT INTO users (id, email, name, password_hash, role, status, created_at, updated_at)
    VALUES (?, ?, ?, ?, 'user', 'active', ?, ?)
  `, [id, normalizedEmail, sanitizeDisplayName(name), passwordHash, now, now]);
  const session = await createSession(id);
  const user = await getUserById(id);
  if (!user) throw httpError(500, "User creation failed");
  return { user: formatUser(user), token: session.token, expiresAt: session.expiresAt };
}

export async function signOut(request: globalThis.Request): Promise<void> {
  const token = readSessionToken(request);
  if (!token) return;
  const tokenHash = hashToken(token);
  await db.run("DELETE FROM sessions WHERE token_hash = ?", [tokenHash]);
}

export async function claimUnownedProjects(userId: string): Promise<number> {
  const result = await db.run("UPDATE projects SET user_id = ? WHERE user_id IS NULL", [userId]);
  return result.changes;
}

export async function getUserById(id: string): Promise<UserRow | undefined> {
  return await db.get<UserRow>("SELECT * FROM users WHERE id = ?", [id]);
}

export async function getUserByEmail(email: string): Promise<UserRow | undefined> {
  return await db.get<UserRow>("SELECT * FROM users WHERE email = ?", [normalizeEmail(email)]);
}

export function hashPassword(password: string): string {
  const salt = randomHex(16);
  const hash = crypto.scryptSync(password, salt, 64).toString("hex");
  return `scrypt$${salt}$${hash}`;
}

function verifyPassword(password: string, hash: string): boolean {
  const [, salt, storedHash] = hash.split("$");
  if (!salt || !storedHash) return false;
  const expected = Buffer.from(storedHash, "hex");
  const actual = crypto.scryptSync(password, salt, 64);
  if (actual.length !== expected.length) return false;
  return crypto.timingSafeEqual(actual, expected);
}

function hashToken(token: string): string {
  return crypto.createHash("sha256").update(token).digest("hex");
}

async function getSessionByToken(token: string): Promise<SessionRow | undefined> {
  return await db.get<SessionRow>("SELECT * FROM sessions WHERE token_hash = ?", [hashToken(token)]);
}

function normalizeEmail(value: string): string {
  return value.trim().toLowerCase();
}

function sanitizeDisplayName(value: string): string {
  return value.trim().slice(0, 80) || localOwnerName;
}

function formatUser(user: UserRow): CurrentUser {
  return {
    id: user.id,
    email: user.email,
    name: user.name,
    role: user.role,
    status: user.status
  };
}
