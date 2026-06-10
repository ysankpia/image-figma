"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiDelete, apiGet, apiPatch, apiPost } from "@/components/api";
import type { ProjectSummary } from "@/shared/types";

export function ProjectWorkspace() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [name, setName] = useState("");
  const [status, setStatus] = useState("正在读取项目。");

  useEffect(() => {
    void loadProjects();
  }, []);

  async function loadProjects() {
    try {
      const data = await apiGet<{ projects: ProjectSummary[] }>("/api/projects");
      setProjects(data.projects);
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

  async function renameProject(project: ProjectSummary) {
    const nextName = window.prompt("项目名称", project.name);
    if (!nextName || nextName.trim() === project.name) return;
    await apiPatch(`/api/projects/${project.id}`, { name: nextName.trim() });
    await loadProjects();
  }

  async function removeProject(project: ProjectSummary) {
    if (!window.confirm(`删除项目“${project.name}”？本地原图、切图记录和导出包会一起删除。`)) return;
    await apiDelete(`/api/projects/${project.id}`);
    await loadProjects();
  }

  return (
    <main className="workspaceShell">
      <header className="workspaceHeader">
        <div>
          <h1>Slice Studio</h1>
          <p>本地项目制 UI 切图工具。上传设计稿截图，手动画出开发需要的 image/icon 资产。</p>
        </div>
        <form
          className="createBar"
          onSubmit={(event) => {
            event.preventDefault();
            void createProject();
          }}
        >
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="项目名称，例如：小程序一期切图" />
          <button type="submit">新建项目</button>
        </form>
      </header>
      <section className="workspaceBody">
        <div className="statusLine">{status}</div>
        {projects.length ? (
          <div className="projectGrid">
            {projects.map((project) => (
              <article key={project.id} className="projectCard">
                <div className="cardTitle">
                  <h2>{project.name}</h2>
                  <span>{new Date(project.updatedAt).toLocaleString("zh-CN")}</span>
                </div>
                <div className="projectStats">
                  <strong>{project.pageCount}</strong>
                  <span>页面</span>
                  <strong>{project.sliceCount}</strong>
                  <span>切图</span>
                </div>
                <div className="cardActions">
                  <Link className="primaryButton" href={`/projects/${project.id}/review`}>打开</Link>
                  <button type="button" onClick={() => void renameProject(project)}>重命名</button>
                  <button type="button" className="dangerButton" onClick={() => void removeProject(project)}>删除</button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="emptyState">没有项目。输入名称后点击“新建项目”。</div>
        )}
      </section>
    </main>
  );
}
