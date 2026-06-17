import type { ReactNode } from "react";
import Link from "next/link";
import { CreditCard, FolderKanban, Settings2, Shield, Sparkles } from "lucide-react";
import { SignOutButton } from "./SignOutButton";

type ConsoleUser = {
  email: string;
  name: string;
  role: string;
  status: string;
};

type ConsoleTab = "projects" | "billing" | "settings" | "admin";

type ConsoleNavItem = {
  id: ConsoleTab;
  label: string;
  href: string;
  icon: typeof FolderKanban;
  adminOnly?: boolean;
};

const tabs: ConsoleNavItem[] = [
  { id: "projects", label: "项目工作台", href: "/projects", icon: FolderKanban },
  { id: "billing", label: "额度与账单", href: "/billing", icon: CreditCard },
  { id: "settings", label: "账号设置", href: "/settings", icon: Settings2 },
  { id: "admin", label: "管理后台", href: "/admin", icon: Shield, adminOnly: true }
];

export function ProductConsoleShell({
  user,
  active,
  eyebrow,
  title,
  description,
  children,
  footerNote
}: {
  user: ConsoleUser;
  active: ConsoleTab;
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
  footerNote?: string;
}) {
  const visibleTabs = tabs.filter((item) => !item.adminOnly || user.role === "admin");

  return (
    <main className="consoleShell">
      <header className="consoleHeaderBand">
        <div className="consoleHeaderInner">
          <div className="consoleTitleBlock">
            <Link className="consoleBrand" href="/">
              <span className="consoleBrandMark">Slice Studio</span>
              <span className="consoleBrandText">把 UI 截图转成可复用资产</span>
            </Link>
            <div className="consoleHeading">
              <p className="eyebrow">{eyebrow}</p>
              <h1>{title}</h1>
              <p>{description}</p>
            </div>
          </div>
          <div className="consoleUserPanel">
            <div className="consoleUserMeta">
              <strong>{user.name}</strong>
              <span>{user.email}</span>
            </div>
            <div className="consoleUserBadges">
              <span className={`statusPill ${user.status}`}>{statusLabel(user.status)}</span>
              <span className="statusPill neutral">{user.role === "admin" ? "管理员" : "普通用户"}</span>
            </div>
            <SignOutButton compact />
          </div>
        </div>
      </header>

      <div className="consoleBody">
        <aside className="consoleSidebar">
          <div className="consoleSidebarSurface">
            <nav className="consoleNav" aria-label="产品导航">
              {visibleTabs.map((item) => {
                const Icon = item.icon;
                const isActive = item.id === active;
                return (
                  <Link key={item.id} href={item.href} className={isActive ? "consoleNavLink active" : "consoleNavLink"}>
                    <Icon aria-hidden="true" />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </nav>
          </div>

          <div className="consoleSidebarNote">
            <Sparkles aria-hidden="true" />
            <div>
              <strong>当前阶段</strong>
              <span>先把账号、项目归属、额度、导出和管理面做顺，支付接入后置。</span>
            </div>
          </div>
        </aside>

        <div className="consoleContent">
          {children}
          {footerNote ? <p className="consoleFooterNote">{footerNote}</p> : null}
        </div>
      </div>
    </main>
  );
}

function statusLabel(status: string): string {
  if (status === "active") return "正常";
  if (status === "suspended") return "已暂停";
  return status;
}
