import Link from "next/link";

export default function HomePage() {
  return (
    <main className="authShell landingShell">
      <section className="authCard landingHero">
        <div>
          <p className="eyebrow">Slice Studio</p>
          <h1>把 UI 截图切成可复用资产</h1>
          <p className="authLead">
            从截图、设计稿、页面原图直接生成可编辑切图、Pencil 项目包和后续可上线的多用户工作流。
          </p>
        </div>
        <div className="landingActions">
          <Link className="primaryButton" href="/login">登录</Link>
          <Link className="secondaryButton" href="/projects">进入工作台</Link>
        </div>
      </section>
      <section className="featureGrid">
        <article className="featureCard"><strong>可编辑切图</strong><span>保存 SliceRecord，导出 assets.zip / project.zip / design.pen。</span></article>
        <article className="featureCard"><strong>文字与物理证据</strong><span>OCR、M29 只做证据输入，不抢最终 ownership。</span></article>
        <article className="featureCard"><strong>多用户底座</strong><span>账号、项目归属、额度、支付和管理入口按 189 路线展开。</span></article>
      </section>
    </main>
  );
}
