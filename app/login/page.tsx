"use client";

import { useState } from "react";
import Link from "next/link";
import { apiPost } from "@/components/api";

type AuthResponse = { user: { email: string; name: string } };

export default function LoginPage() {
  const [mode, setMode] = useState<"sign-in" | "sign-up">("sign-in");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState(" ");
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    setStatus("正在提交...");
    try {
      if (mode === "sign-up") {
        await apiPost<AuthResponse>("/api/auth/sign-up", { name, email, password });
      } else {
        await apiPost<AuthResponse>("/api/auth/sign-in", { email, password });
      }
      window.location.href = "/projects";
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "登录失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="authShell">
      <section className="authCard">
        <p className="eyebrow">Slice Studio</p>
        <h1>{mode === "sign-up" ? "创建账号" : "登录"}</h1>
        <p className="authLead">先把会话打通，再谈额度、支付和管理后台。本地默认管理员：local@slicestudio.dev / slice-studio-local-owner。</p>
        <div className="authTabs">
          <button type="button" className={mode === "sign-in" ? "active" : ""} onClick={() => setMode("sign-in")}>登录</button>
          <button type="button" className={mode === "sign-up" ? "active" : ""} onClick={() => setMode("sign-up")}>注册</button>
        </div>
        <div className="authForm">
          {mode === "sign-up" ? (
            <label htmlFor="auth-name">
              <span>昵称</span>
              <input id="auth-name" name="name" value={name} onChange={(event) => setName(event.target.value)} placeholder="你的名字" autoComplete="name" />
            </label>
          ) : null}
          <label htmlFor="auth-email">
            <span>邮箱</span>
            <input id="auth-email" name="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="name@example.com" autoComplete="email" />
          </label>
          <label htmlFor="auth-password">
            <span>密码</span>
            <input id="auth-password" name="password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="至少 8 位" autoComplete={mode === "sign-up" ? "new-password" : "current-password"} />
          </label>
          <button type="button" className="primaryButton" disabled={busy} onClick={() => void submit()}>{mode === "sign-up" ? "注册并进入" : "登录"}</button>
          <div className="statusLine">{status}</div>
          <Link href="/" className="inlineLink">返回首页</Link>
        </div>
      </section>
    </main>
  );
}
