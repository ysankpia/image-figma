import { redirect } from "next/navigation";
import { ProjectWorkspace } from "@/components/workspace/ProjectWorkspace";
import { fetchCurrentUser } from "@/app/server-auth";

export default async function ProjectsPage() {
  const user = await fetchCurrentUser().catch(() => null);
  if (!user) redirect("/login");
  return <ProjectWorkspace />;
}
