"use client";

import Link from "next/link";
import { Check, FileImage, Grid3X3, LayoutList, LogOut, Pencil, Plus, Search, Trash2, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { apiDelete, apiGet, apiPatch, apiPost, apiUrl } from "@/components/api";
import type { ProjectListItem, ProjectSummary } from "@/shared/types";

type ProjectFilter = "recent" | "all" | "withSlices";
type SortMode = "updated" | "name" | "pages";
type ViewMode = "grid" | "list";

type ProjectCardModel = ProjectSummary & {
  previewUrl: string | null;
  firstPageName: string | null;
  firstPageSize: string | null;
};

export function ProjectWorkspace() {
  const [projects, setProjects] = useState<ProjectCardModel[]>([]);
  const [name, setName] = useState("");
  const [status, setStatus] = useState("正在读取项目。");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<ProjectFilter>("recent");
  const [sortMode, setSortMode] = useState<SortMode>("updated");
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [editingProjectId, setEditingProjectId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState("");
  const [pendingDeleteProject, setPendingDeleteProject] = useState<ProjectCardModel | null>(null);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [account, setAccount] = useState<{ email: string; name: string } | null>(null);

  useEffect(() => {
    void loadSession();
    void loadProjects();
  }, []);

  async function loadSession() {
    try {
      const data = await apiGet<{ user: { email: string; name: string } | null }>("/api/auth/session");
      if (!data.user) {
        window.location.href = "/login";
        return;
      }
      setAccount(data.user);
    } catch {
      window.location.href = "/login";
    }
  }

  async function loadProjects() {
    try {
      const data = await apiGet<{ projects: ProjectListItem[] }>("/api/projects");
      const enriched = data.projects.map((project) => ({
        ...project,
        previewUrl: project.firstPage?.sourceUrl ? resolveApiUrl(project.firstPage.sourceUrl) : null,
        firstPageName: project.firstPage ? project.firstPage.displayName || project.firstPage.originalName : null,
        firstPageSize: project.firstPage ? `${project.firstPage.width}x${project.firstPage.height}` : null
      }));
      setProjects(enriched);
      setStatus(data.projects.length ? `共 ${data.projects.length} 个项目。` : "还没有项目。新建一个项目开始切图。");
    } catch (error) {
      setStatus(`读取失败：${error instanceof Error ? error.message : "unknown error"}`);
    }
  }

  async function createProject() {
    const projectName = name.trim() || `未命名项目 ${new Date().toLocaleString("zh-CN")}`;
    const data = await apiPost<{ project: ProjectSummary }>("/api/projects", { name: projectName });
    window.location.href = `/projects/${data.project.id}/review`;
  }

  function closeCreateDialog() {
    setCreateDialogOpen(false);
    setName("");
  }

  function startRenameProject(project: ProjectSummary) {
    setEditingProjectId(project.id);
    setEditingName(project.name);
  }

  function cancelRenameProject() {
    setEditingProjectId(null);
    setEditingName("");
  }

  async function submitRenameProject(project: ProjectSummary) {
    const nextName = editingName.trim();
    if (!nextName || nextName === project.name) {
      cancelRenameProject();
      return;
    }
    await apiPatch(`/api/projects/${project.id}`, { name: nextName });
    cancelRenameProject();
    await loadProjects();
  }

  async function removeProject(project: ProjectSummary) {
    await apiDelete(`/api/projects/${project.id}`);
    setPendingDeleteProject(null);
    await loadProjects();
  }

  async function signOut() {
    await apiPost("/api/auth/sign-out", {});
    window.location.href = "/";
  }

  const filteredProjects = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    const result = projects.filter((project) => {
      if (filter === "withSlices" && project.sliceCount === 0) return false;
      if (!normalizedQuery) return true;
      return [project.name, project.firstPageName || ""].some((value) => value.toLowerCase().includes(normalizedQuery));
    });
    result.sort((a, b) => {
      if (sortMode === "name") return a.name.localeCompare(b.name, "zh-CN");
      if (sortMode === "pages") return b.pageCount - a.pageCount || Date.parse(b.updatedAt) - Date.parse(a.updatedAt);
      return Date.parse(b.updatedAt) - Date.parse(a.updatedAt);
    });
    return result;
  }, [filter, projects, query, sortMode]);

  return (
    <main className="workspaceShell">
      <section className="workspaceMain">
        <header className="workspaceTopbar">
          <div className="workspaceCrumbs">
            <span>Slice Studio</span>
            <strong>{filter === "withSlices" ? "With assets" : filter === "all" ? "All projects" : "Recents"}</strong>
          </div>
          <div className="workspaceAccount">
            {account ? <span>{account.name || account.email}</span> : null}
            <Link href="/settings">设置</Link>
            <Link href="/billing">账单</Link>
            <Link href="/admin">管理</Link>
            <button type="button" aria-label="退出登录" onClick={() => void signOut()}>
              <LogOut aria-hidden="true" />
            </button>
            <button type="button" className="newProjectButton" onClick={() => setCreateDialogOpen(true)}>
              <Plus aria-hidden="true" />
              新建项目
            </button>
          </div>
        </header>

        <div className="workspaceContent">
          <div className="workspaceSectionBar">
            <div className="workspaceTabs" role="tablist" aria-label="项目过滤">
              <button type="button" className={filter === "recent" ? "active" : ""} onClick={() => setFilter("recent")}>最近查看</button>
              <button type="button" className={filter === "all" ? "active" : ""} onClick={() => setFilter("all")}>全部项目</button>
              <button type="button" className={filter === "withSlices" ? "active" : ""} onClick={() => setFilter("withSlices")}>已有切图</button>
            </div>
            <div className="workspaceControls">
              <label className="workspaceSearch">
                <Search aria-hidden="true" />
                <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索项目" />
              </label>
              <select value={sortMode} onChange={(event) => setSortMode(event.target.value as SortMode)} aria-label="排序方式">
                <option value="updated">最近更新</option>
                <option value="name">项目名称</option>
                <option value="pages">页面数量</option>
              </select>
              <div className="viewSwitch" aria-label="视图模式">
                <button type="button" className={viewMode === "grid" ? "active" : ""} aria-label="网格视图" onClick={() => setViewMode("grid")}>
                  <Grid3X3 aria-hidden="true" />
                </button>
                <button type="button" className={viewMode === "list" ? "active" : ""} aria-label="列表视图" onClick={() => setViewMode("list")}>
                  <LayoutList aria-hidden="true" />
                </button>
              </div>
            </div>
          </div>

          <div className="statusLine">{status}{query ? ` 当前筛选 ${filteredProjects.length} 个。` : ""}</div>

          {filteredProjects.length ? (
            <div className={viewMode === "grid" ? "projectGrid" : "projectList"}>
              {filteredProjects.map((project) => (
                <ProjectCard
                  key={project.id}
                  project={project}
                  viewMode={viewMode}
                  isEditing={editingProjectId === project.id}
                  editingName={editingName}
                  onEditingNameChange={setEditingName}
                  onStartRename={() => startRenameProject(project)}
                  onCancelRename={cancelRenameProject}
                  onSubmitRename={() => void submitRenameProject(project)}
                  onRequestRemove={() => setPendingDeleteProject(project)}
                />
              ))}
            </div>
          ) : (
            <div className="emptyState">
              <FileImage aria-hidden="true" />
              <strong>{projects.length ? "没有匹配项目" : "没有项目"}</strong>
              <span>{projects.length ? "换一个搜索词或过滤条件。" : "输入名称后点击“新建”。"}</span>
            </div>
          )}
        </div>
      </section>
      {createDialogOpen ? (
        <div className="modalBackdrop" role="presentation" onMouseDown={closeCreateDialog}>
          <section
            className="confirmDialog createProjectDialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="create-project-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <button type="button" className="dialogCloseButton" aria-label="关闭" onClick={closeCreateDialog}>
              <X aria-hidden="true" />
            </button>
            <div className="dialogIcon primary">
              <FileImage aria-hidden="true" />
            </div>
            <div className="dialogText">
              <h2 id="create-project-title">新建项目</h2>
              <p>创建一个本地切图项目，然后上传 UI 截图开始画框。</p>
            </div>
            <form
              className="createProjectForm"
              onSubmit={(event) => {
                event.preventDefault();
                void createProject();
              }}
            >
              <label>
                <span>项目名称</span>
                <input autoFocus value={name} onChange={(event) => setName(event.target.value)} placeholder="例如：小程序一期切图" />
              </label>
              <div className="dialogActions">
                <button type="button" onClick={closeCreateDialog}>取消</button>
                <button type="submit" className="primaryConfirmButton">创建项目</button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
      {pendingDeleteProject ? (
        <div className="modalBackdrop" role="presentation" onMouseDown={() => setPendingDeleteProject(null)}>
          <section
            className="confirmDialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-project-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <button type="button" className="dialogCloseButton" aria-label="关闭" onClick={() => setPendingDeleteProject(null)}>
              <X aria-hidden="true" />
            </button>
            <div className="dialogIcon danger">
              <Trash2 aria-hidden="true" />
            </div>
            <div className="dialogText">
              <h2 id="delete-project-title">删除这个项目？</h2>
              <p>“{pendingDeleteProject.name}” 的本地原图、切图记录和导出包都会一起删除。这个操作不能撤销。</p>
            </div>
            <div className="dialogActions">
              <button type="button" onClick={() => setPendingDeleteProject(null)}>取消</button>
              <button type="button" className="dangerConfirmButton" onClick={() => void removeProject(pendingDeleteProject)}>确认删除</button>
            </div>
          </section>
        </div>
      ) : null}
    </main>
  );
}

function resolveApiUrl(path: string): string {
  if (/^https?:\/\//.test(path)) return path;
  return apiUrl(path);
}

function ProjectCard({
  project,
  viewMode,
  isEditing,
  editingName,
  onEditingNameChange,
  onStartRename,
  onCancelRename,
  onSubmitRename,
  onRequestRemove
}: {
  project: ProjectCardModel;
  viewMode: ViewMode;
  isEditing: boolean;
  editingName: string;
  onEditingNameChange: (name: string) => void;
  onStartRename: () => void;
  onCancelRename: () => void;
  onSubmitRename: () => void;
  onRequestRemove: () => void;
}) {
  const updated = new Date(project.updatedAt).toLocaleString("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });
  const isList = viewMode === "list";

  return (
    <article className={isList ? "projectCard list" : "projectCard"}>
      <Link className="projectPreviewLink" href={`/projects/${project.id}/review`} aria-label={`打开 ${project.name}`}>
        <div className="projectPreview">
          {project.previewUrl ? (
            <img src={project.previewUrl} alt="" loading="lazy" />
          ) : (
            <div className="projectPreviewEmpty">
              <FileImage aria-hidden="true" />
            </div>
          )}
        </div>
      </Link>
      <div className="projectMeta">
        <div className="projectIcon">
          <FileImage aria-hidden="true" />
        </div>
        <div className="projectTitleBlockCard">
          {isEditing ? (
            <form
              className="renameProjectForm"
              onSubmit={(event) => {
                event.preventDefault();
                onSubmitRename();
              }}
            >
              <input
                autoFocus
                value={editingName}
                onChange={(event) => onEditingNameChange(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Escape") onCancelRename();
                }}
                aria-label="项目名称"
              />
            </form>
          ) : (
            <Link href={`/projects/${project.id}/review`}>{project.name}</Link>
          )}
          <span>{project.pageCount ? `Edited ${updated}` : "Empty project"}</span>
          {isList ? <span>{project.firstPageName || "尚未上传页面"}{project.firstPageSize ? ` · ${project.firstPageSize}` : ""}</span> : null}
        </div>
        <div className="projectBadges">
          <span>{project.pageCount} 页</span>
          <span>{project.sliceCount} 切图</span>
        </div>
        <div className="cardActions">
          {isEditing ? (
            <>
              <button type="button" className="confirmEditButton" onClick={onSubmitRename} aria-label="保存项目名称">
                <Check aria-hidden="true" />
              </button>
              <button type="button" onClick={onCancelRename} aria-label="取消重命名">
                <X aria-hidden="true" />
              </button>
            </>
          ) : (
            <>
              <button type="button" onClick={onStartRename} aria-label={`重命名 ${project.name}`}>
                <Pencil aria-hidden="true" />
              </button>
              <button type="button" className="dangerButton" onClick={onRequestRemove} aria-label={`删除 ${project.name}`}>
                <Trash2 aria-hidden="true" />
              </button>
            </>
          )}
        </div>
      </div>
    </article>
  );
}
