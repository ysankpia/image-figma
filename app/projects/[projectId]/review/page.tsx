import { ReviewWorkbench } from "@/components/review/ReviewWorkbench";

export default async function ReviewPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  return <ReviewWorkbench projectId={projectId} />;
}
