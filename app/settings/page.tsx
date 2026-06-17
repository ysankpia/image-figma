import Link from "next/link";
import { redirect } from "next/navigation";
import { fetchCurrentUser } from "@/app/server-auth";

export default async function SettingsPage() {
  const user = await fetchCurrentUser().catch(() => null);
  if (!user) redirect("/login");

  return (
    <main className="accountShell">
      <nav className="accountNav">
        <Link href="/projects">项目</Link>
        <Link href="/billing">账单</Link>
        <Link href="/admin">管理</Link>
      </nav>
      <section className="accountPanel">
        <p className="eyebrow">Account</p>
        <h1>账号设置</h1>
        <dl className="accountFacts">
          <div><dt>邮箱</dt><dd>{user.email}</dd></div>
          <div><dt>昵称</dt><dd>{user.name}</dd></div>
          <div><dt>角色</dt><dd>{user.role}</dd></div>
          <div><dt>状态</dt><dd>{user.status}</dd></div>
        </dl>
        <p className="accountNote">密码修改、第三方登录绑定、数据导出和删除请求会在后续生产阶段接入；当前阶段先固定会话和项目归属边界。</p>
      </section>
    </main>
  );
}
