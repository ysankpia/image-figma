import { redirect } from "next/navigation";
import { fetchCurrentUser } from "@/app/server-auth";
import { SignOutButton } from "@/components/site/SignOutButton";
import { WorkbenchPreferencesForm } from "@/components/site/WorkbenchPreferencesForm";

export default async function SettingsPage() {
  const user = await fetchCurrentUser().catch(() => null);
  if (!user) redirect("/login");

  return (
    <main className="settingsPage">
      <header className="settingsHeader">
        <a className="consoleBrand inline" href="/projects">Slice Studio</a>
        <div>
          <p className="eyebrow">Account</p>
          <h1>账号设置</h1>
          <p>查看当前登录账号，并调整这个浏览器上的工作台使用偏好。</p>
        </div>
      </header>

      <section className="settingsPanel">
        <div className="sectionHeader">
          <div>
            <h2>账号概览</h2>
            <p>这些字段用于项目归属、原图访问、切图保存和导出下载。</p>
          </div>
        </div>
        <dl className="metricGrid metricGridCompact">
          <div className="metricCard">
            <dt>邮箱</dt>
            <dd>{user.email}</dd>
          </div>
          <div className="metricCard">
            <dt>昵称</dt>
            <dd>{user.name}</dd>
          </div>
          <div className="metricCard">
            <dt>状态</dt>
            <dd>{user.status === "active" ? "正常" : "已暂停"}</dd>
          </div>
        </dl>
      </section>

      <section className="settingsPanel">
        <div className="sectionHeader">
          <div>
            <h2>工作台偏好</h2>
            <p>这些设置只影响当前浏览器，用来把单人切图流程调到最顺手。</p>
          </div>
        </div>
        <WorkbenchPreferencesForm />
      </section>

      <section className="settingsPanel">
        <div className="sectionHeader">
          <div>
            <h2>当前会话</h2>
            <p>退出后需要重新登录才能进入项目工作台。</p>
          </div>
        </div>
        <div className="inlineActionRow">
          <SignOutButton label="退出当前会话" />
        </div>
      </section>
    </main>
  );
}
