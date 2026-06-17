import { redirect } from "next/navigation";
import { ReviewWorkbench } from "@/components/review/ReviewWorkbench";
import { fetchCurrentUser } from "@/app/server-auth";

export default async function ReviewPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  const user = await fetchCurrentUser().catch(() => null);
  if (!user) redirect("/login");
  return <ReviewWorkbench projectId={projectId} />;
}
