"use client";

"use client";

import dynamic from "next/dynamic";

const ReviewWorkbenchClient = dynamic(() => import("./ReviewWorkbenchClient").then((module) => module.ReviewWorkbenchClient), {
  ssr: false,
  loading: () => <main className="reviewShell"><div className="emptyState">正在加载画布。</div></main>
});

export function ReviewWorkbench({ projectId }: { projectId: string }) {
  return <ReviewWorkbenchClient projectId={projectId} />;
}
