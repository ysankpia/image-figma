"use client";

import Link from "next/link";
import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";
import { apiPost } from "@/components/api";

type AuthMode = "sign-in" | "sign-up";
type AuthResponse = { user: { email: string; name: string } };

export function AuthFormCard({
  mode,
  devHint
}: {
  mode: AuthMode;
  devHint?: string | null;
}) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const isSignUp = mode === "sign-up";

  async function submit() {
    if (busy) return;
    setBusy(true);
    setStatus(isSignUp ? "正在创建账号..." : "正在登录...");
    try {
      if (isSignUp) {
        await apiPost<AuthResponse>("/api/auth/sign-up", { name, email, password });
      } else {
        await apiPost<AuthResponse>("/api/auth/sign-in", { email, password });
      }
      window.location.href = "/projects";
    } catch (error) {
      setStatus(error instanceof Error ? error.message : isSignUp ? "注册失败" : "登录失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="authPage">
      <section className="authShowcase">
        <div className="authShowcaseOverlay" />
        <div className="authShowcaseBody">
          <div className="authShowcaseCopy">
            <p className="eyebrow">Slice Studio</p>
            <h1>把截图直接推进到可编辑资产交付</h1>
            <p>
              面向设计师、前端独立开发者、外包团队和小程序开发者。先完成项目归属、额度和导出主链路，再把支付与多用户运营收口。
            </p>
          </div>
          <div className="authShowcasePanel">
            <strong>当前这套产品已经在做的事</strong>
            <ul className="authFeatureList">
              <li>项目内直接管理原图、切图和导出包</li>
              <li>AI 识别、手动画框、可编辑文字重建在一条主链路里完成</li>
              <li>额度、账号和管理面已经并入同一套产品壳</li>
            </ul>
          </div>
        </div>
      </section>

      <section className="authPanel">
        <div className="authPanelHeader">
          <Link className="consoleBrand inline" href="/">Slice Studio</Link>
          <div>
            <h2>{isSignUp ? "创建账号" : "登录账号"}</h2>
            <p>{isSignUp ? "创建一个账号，直接进入你的项目工作台。" : "继续处理你的项目、额度和导出流程。"}</p>
          </div>
        </div>

        <form
          className="authForm"
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          {isSignUp ? (
            <label className="formField" htmlFor="auth-name">
              <span>昵称</span>
              <input
                id="auth-name"
                name="name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                autoComplete="name"
                placeholder="你的名字"
                required
              />
            </label>
          ) : null}

          <label className="formField" htmlFor="auth-email">
            <span>邮箱</span>
            <input
              id="auth-email"
              name="email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email username"
              inputMode="email"
              placeholder="name@example.com"
              required
            />
          </label>

          <label className="formField" htmlFor="auth-password">
            <span>密码</span>
            <div className="passwordField">
              <input
                id="auth-password"
                name="password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete={isSignUp ? "new-password" : "current-password"}
                placeholder={isSignUp ? "至少 8 位，建议包含字母和数字" : "输入当前密码"}
                minLength={8}
                required
              />
              <button
                type="button"
                className="passwordToggle"
                aria-label={showPassword ? "隐藏密码" : "显示密码"}
                onClick={() => setShowPassword((value) => !value)}
              >
                {showPassword ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}
              </button>
            </div>
          </label>

          <button type="submit" className="primaryButton authSubmitButton" disabled={busy}>
            {isSignUp ? "注册并进入工作台" : "登录并进入工作台"}
          </button>

          <div className="authHelperRow">
            <span>{isSignUp ? "已经有账号？" : "还没有账号？"}</span>
            <Link href={isSignUp ? "/login" : "/register"}>{isSignUp ? "去登录" : "创建账号"}</Link>
          </div>

          <div className="statusLine authStatus" aria-live="polite">
            {status || " "}
          </div>

          {devHint ? <p className="authDevHint">{devHint}</p> : null}
        </form>
      </section>
    </main>
  );
}
