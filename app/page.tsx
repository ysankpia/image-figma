import Image from "next/image";
import Link from "next/link";

const highlights = [
  { label: "交付物", value: "assets.zip / design.pen / 项目包" },
  { label: "目标用户", value: "设计师、独立开发者、外包团队" },
  { label: "当前主线", value: "项目归属、额度、导出、管理面" }
];

const workflowSteps = [
  {
    step: "01",
    title: "上传截图并组织项目",
    description: "项目内直接保存原图、页面顺序和切片结果，不再靠零散文件夹拼交付。"
  },
  {
    step: "02",
    title: "AI 辅助识别，人工复核",
    description: "AI 给建议框，人工修正后再保存，避免让模型直接越权成为导出真相源。"
  },
  {
    step: "03",
    title: "导出资产包与设计稿包",
    description: "同一条主链路输出 assets.zip、design.pen 和项目包，真正可交付，不是 Demo。"
  }
];

const productSurfaces = [
  {
    title: "项目工作台",
    description: "管理页面、切片、导出和回看记录。当前最成熟、最该稳定的一层。"
  },
  {
    title: "账号与额度",
    description: "项目归属、用量、套餐和账单都在同一个产品壳下继续收口。"
  },
  {
    title: "运营与纠偏",
    description: "管理端先满足真实运营动作：看规模、修权益、查订单，再谈更复杂的后台。"
  }
];

export default function HomePage() {
  return (
    <main className="marketingPage">
      <header className="siteHeader">
        <Link className="consoleBrand" href="/">
          <span className="consoleBrandMark">Slice Studio</span>
          <span className="consoleBrandText">把 UI 截图转成可复用资产</span>
        </Link>
        <nav className="siteHeaderNav">
          <Link href="/projects">工作台</Link>
          <Link href="/login">登录</Link>
          <Link className="primaryButton" href="/register">创建账号</Link>
        </nav>
      </header>

      <section className="marketingHero">
        <Image
          src="/marketing/workspace-hero.png"
          alt="Slice Studio 项目工作台截图"
          fill
          priority
          className="marketingHeroImage"
        />
        <div className="marketingHeroShade" />
        <div className="marketingHeroInner">
          <div className="marketingHeroCopy">
            <p className="eyebrow">可编辑资产交付</p>
            <h1>把 UI 截图直接推进到可复用资产和设计稿交付</h1>
            <p className="marketingLead">
              用一条主链路处理截图上传、AI 辅助画框、手动修正、导出资产包和 Pencil 项目包。不是演示页，是实际能交付的工作台。
            </p>
            <div className="landingActions">
              <Link className="primaryButton" href="/register">开始创建账号</Link>
              <Link className="secondaryButton ghost" href="/projects">直接进入工作台</Link>
            </div>
          </div>
          <div className="heroStatRow">
            {highlights.map((item) => (
              <div key={item.label} className="heroStat">
                <span>{item.label}</span>
                <strong>{item.value}</strong>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="marketingBand">
        <div className="marketingSection">
          <div className="bandHeader">
            <p className="eyebrow">工作方式</p>
            <h2>先把交付主链路做顺，再把多用户 SaaS 收口</h2>
          </div>
          <div className="workflowGrid">
            {workflowSteps.map((item) => (
              <article key={item.step} className="workflowCard">
                <span className="workflowStep">{item.step}</span>
                <strong>{item.title}</strong>
                <p>{item.description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="marketingBand subtle">
        <div className="marketingSection">
          <div className="deliverableRow">
            <div>
              <p className="eyebrow">产品面</p>
              <h2>不是只有一个切图画布，而是一整套可上线的产品壳</h2>
            </div>
            <p className="marketingNote">
              当前优先级很明确：先把项目工作台、账号归属、额度、导出和运营入口做成可正式使用的产品，再把支付接回。
            </p>
          </div>
          <div className="surfaceGrid">
            {productSurfaces.map((item) => (
              <article key={item.title} className="surfaceCard">
                <strong>{item.title}</strong>
                <p>{item.description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="marketingBand compact">
        <div className="marketingSection">
          <div className="deliverableRow">
            <div>
              <p className="eyebrow">交付对象</p>
              <h2>设计师、前端独立开发者、外包团队、小程序开发者</h2>
            </div>
            <p className="marketingNote">
              中文优先。后续再补英文、支付和正式商业化入口；当前重点是把实际工作流做成稳定的 SaaS 主链路。
            </p>
          </div>
          <div className="featureGrid">
            <article className="featureCard">
              <strong>项目内完成切图</strong>
              <span>上传原图、保存切片、持续修改，项目本身就是你的交付真相源。</span>
            </article>
            <article className="featureCard">
              <strong>证据驱动的文字重建</strong>
              <span>OCR、M29 和文本样式测量只负责提供证据，真正导出仍由保存结果控制。</span>
            </article>
            <article className="featureCard">
              <strong>生产化底座已经并进来</strong>
              <span>账号、项目归属、额度、管理面和下载权限都在同一套产品壳里继续收口。</span>
            </article>
          </div>
        </div>
      </section>
    </main>
  );
}
