"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, Download, GripHorizontal, Hand, Images, MousePointer2, PanelRightClose, PanelRightOpen, RotateCcw, Square, Trash2, Upload, X } from "lucide-react";
import { Image as KonvaImage, Layer, Rect, Stage, Text, Transformer } from "react-konva";
import type Konva from "konva";
import { apiBaseUrl, apiGet, apiPost, deletePage, renamePage, reorderPages, replacePage, saveSlices, uploadPages } from "@/components/api";
import { draftToBox, normalizeBox } from "@/shared/bbox";
import type { BBox, PageRecord, ProjectDetail, SaveState, SliceRecord, ToolMode } from "@/shared/types";

type WorkbenchPage = PageRecord & {
  slices: SliceRecord[];
  image: HTMLImageElement | null;
};

type DragState =
  | { type: "draw"; start: Point; current: Point }
  | { type: "pan"; startClient: Point; originalPosition: Point };

type Point = { x: number; y: number };

type UndoSnapshot = {
  label: string;
  pages: WorkbenchPage[];
  activePageId: string | null;
  activeSliceId: string | null;
  status?: string;
  sourceFileAction?: boolean;
};

type PageConfirmAction =
  | { type: "delete"; pageId: string }
  | { type: "replace"; pageId: string; file: File };

const transformerAnchors = ["top-left", "top-center", "top-right", "middle-right", "bottom-right", "bottom-center", "bottom-left", "middle-left"];
const reviewColorStorageKey = "sliceStudio.reviewBoxColors.v1";
const defaultBoxColors = {
  slice: "#0066cc",
  active: "#ff2d55"
};

export function ReviewWorkbenchClient({ projectId }: { projectId: string }) {
  const [detail, setDetail] = useState<ProjectDetail | null>(null);
  const [pages, setPages] = useState<WorkbenchPage[]>([]);
  const [activePageId, setActivePageId] = useState<string | null>(null);
  const [activeSliceId, setActiveSliceId] = useState<string | null>(null);
  const [tool, setTool] = useState<ToolMode>("select");
  const [scale, setScale] = useState(1);
  const [stagePosition, setStagePosition] = useState<Point>({ x: 80, y: 80 });
  const [drag, setDrag] = useState<DragState | null>(null);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [status, setStatus] = useState("正在读取项目。");
  const [stageSize, setStageSize] = useState({ width: 1000, height: 700 });
  const [inspectorCollapsed, setInspectorCollapsed] = useState(false);
  const [undoStack, setUndoStack] = useState<UndoSnapshot[]>([]);
  const [pageConfirmAction, setPageConfirmAction] = useState<PageConfirmAction | null>(null);
  const [draggingPageId, setDraggingPageId] = useState<string | null>(null);
  const [boxColors, setBoxColors] = useState(defaultBoxColors);
  const stageWrapRef = useRef<HTMLDivElement | null>(null);
  const stageRef = useRef<Konva.Stage | null>(null);
  const transformerRef = useRef<Konva.Transformer | null>(null);
  const activeRectRef = useRef<Konva.Rect | null>(null);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pageRenameTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingPageRenameRef = useRef<{ pageId: string; displayName: string } | null>(null);
  const pageRenameUndoRef = useRef<string | null>(null);
  const sliceEditUndoRef = useRef<string | null>(null);
  const replaceInputRef = useRef<HTMLInputElement | null>(null);

  const activePage = pages.find((page) => page.id === activePageId) || null;
  const activeSlice = activePage?.slices.find((slice) => slice.id === activeSliceId) || null;
  const hasSlices = pages.some((page) => page.slices.length > 0);
  const totalAssets = pages.reduce((total, page) => total + page.slices.length, 0);
  const activePageAssetCount = activePage?.slices.length || 0;
  const saveLabel = saveState === "saving" ? "保存中" : saveState === "saved" ? "已保存" : saveState === "error" ? "保存失败" : "就绪";
  const pageIndex = activePage ? pages.findIndex((page) => page.id === activePage.id) : -1;

  const loadProject = useCallback(async () => {
    const projectDetail = await apiGet<ProjectDetail>(`/api/projects/${projectId}`);
    const hydratedPages = await hydratePages(projectDetail.pages);
    setDetail(projectDetail);
    setPages(hydratedPages);
    setActivePageId(hydratedPages[0]?.id || null);
    setActiveSliceId(null);
    setStatus(hydratedPages.length ? "项目已恢复。继续切图会自动保存。" : "项目已创建。上传 UI 截图开始。");
  }, [projectId]);

  useEffect(() => {
    void loadProject().catch((error) => setStatus(`读取失败：${error instanceof Error ? error.message : "unknown error"}`));
  }, [loadProject]);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(reviewColorStorageKey);
      if (!raw) return;
      const parsed = JSON.parse(raw) as Partial<typeof defaultBoxColors>;
      setBoxColors({
        slice: normalizeColor(parsed.slice, defaultBoxColors.slice),
        active: normalizeColor(parsed.active, defaultBoxColors.active)
      });
    } catch {
      setBoxColors(defaultBoxColors);
    }
  }, []);

  useEffect(() => {
    const resize = () => {
      const rect = stageWrapRef.current?.getBoundingClientRect();
      if (rect) setStageSize({ width: Math.max(480, rect.width), height: Math.max(360, rect.height) });
    };
    resize();
    const observer = typeof ResizeObserver !== "undefined" && stageWrapRef.current ? new ResizeObserver(resize) : null;
    if (stageWrapRef.current) observer?.observe(stageWrapRef.current);
    window.addEventListener("resize", resize);
    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", resize);
    };
  }, []);

  useEffect(() => {
    if (transformerRef.current && activeRectRef.current && tool === "select") {
      transformerRef.current.nodes([activeRectRef.current]);
      transformerRef.current.getLayer()?.batchDraw();
    }
  }, [activeSliceId, tool, pages]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName)) {
        if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "z") {
          event.preventDefault();
          void restoreUndo();
        }
        return;
      }
      if (event.key.toLowerCase() === "v") setTool("select");
      if (event.key.toLowerCase() === "b") setTool("draw");
      if (event.key.toLowerCase() === "h") setTool("pan");
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "z") {
        event.preventDefault();
        void restoreUndo();
        return;
      }
      if (event.key === "Delete" || event.key === "Backspace") {
        event.preventDefault();
        deleteActiveSlice();
      }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        void saveNow().catch(() => undefined);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  });

  async function hydratePage(page: ProjectDetail["pages"][number]): Promise<WorkbenchPage> {
    return {
      ...page,
      image: await loadImage(`${apiBaseUrl}${page.sourceUrl}`)
    };
  }

  async function hydratePages(sourcePages: ProjectDetail["pages"]): Promise<WorkbenchPage[]> {
    return Promise.all(sourcePages.map(hydratePage));
  }

  async function applyProjectDetail(projectDetail: ProjectDetail, nextActivePageId?: string | null, nextActiveSliceId?: string | null) {
    const hydratedPages = await hydratePages(projectDetail.pages);
    setDetail(projectDetail);
    setPages(hydratedPages);
    const resolvedPageId = nextActivePageId && hydratedPages.some((page) => page.id === nextActivePageId)
      ? nextActivePageId
      : hydratedPages[0]?.id || null;
    setActivePageId(resolvedPageId);
    const activePageForSlice = hydratedPages.find((page) => page.id === resolvedPageId);
    setActiveSliceId(nextActiveSliceId && activePageForSlice?.slices.some((slice) => slice.id === nextActiveSliceId) ? nextActiveSliceId : null);
  }

  function clonePagesForUndo(sourcePages = pages): WorkbenchPage[] {
    return sourcePages.map((page) => ({
      ...page,
      slices: page.slices.map((slice) => ({ ...slice, bbox: { ...slice.bbox } }))
    }));
  }

  function pushUndo(label: string, options: { sourceFileAction?: boolean } = {}) {
    setUndoStack((current) => [
      ...current.slice(-19),
      {
        label,
        pages: clonePagesForUndo(),
        activePageId,
        activeSliceId,
        status,
        sourceFileAction: options.sourceFileAction
      }
    ]);
  }

  async function restoreUndo() {
    const snapshot = undoStack[undoStack.length - 1];
    if (!snapshot) return;
    clearPendingSaves();
    setUndoStack((current) => current.slice(0, -1));
    if (snapshot.sourceFileAction) {
      setStatus("该操作涉及页面原图文件，无法完整撤销；已按当前磁盘状态重新载入项目。");
      await loadProject();
      return;
    }

    const restoredPages = clonePagesForUndo(snapshot.pages);
    setPages(restoredPages);
    setActivePageId(snapshot.activePageId);
    setActiveSliceId(snapshot.activeSliceId);
    setStatus(`已撤销：${snapshot.label}`);
    setSaveState("saving");
    try {
      await reorderPages(projectId, restoredPages.map((page) => page.id));
      await Promise.all(restoredPages.map((page) => renamePage(projectId, page.id, page.displayName)));
      await saveSlices(projectId, serializeSlices(restoredPages, snapshot.activePageId));
      setSaveState("saved");
    } catch (error) {
      setSaveState("error");
      setStatus(`撤销保存失败：${error instanceof Error ? error.message : "unknown error"}`);
    }
  }

  function clearPendingSaves() {
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
    if (pageRenameTimerRef.current) {
      clearTimeout(pageRenameTimerRef.current);
      pageRenameTimerRef.current = null;
    }
    pendingPageRenameRef.current = null;
    pageRenameUndoRef.current = null;
    sliceEditUndoRef.current = null;
  }

  async function handleUpload(files: FileList | null) {
    const images = Array.from(files || []).filter((file) => file.type.startsWith("image/"));
    if (!images.length) return;
    try {
      setStatus(`正在上传 ${images.length} 张图片。`);
      await uploadPages(projectId, images);
      await loadProject();
      setStatus(`已上传 ${images.length} 张图片。`);
    } catch (error) {
      setStatus(`上传失败：${error instanceof Error ? error.message : "unknown error"}`);
    }
  }

  function scheduleSave(nextPages: WorkbenchPage[], options: { pushUndo?: boolean; undoLabel?: string } = {}) {
    if (options.pushUndo) pushUndo(options.undoLabel || "编辑");
    setPages(nextPages);
    setSaveState("saving");
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      void saveNow(nextPages).catch(() => undefined);
    }, 800);
  }

  async function saveNow(pagesToSave = pages) {
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
    setSaveState("saving");
    try {
      await saveSlices(projectId, serializeSlices(pagesToSave, activePageId));
      setSaveState("saved");
      setStatus("已保存。");
    } catch (error) {
      setSaveState("error");
      setStatus(`保存失败：${error instanceof Error ? error.message : "unknown error"}`);
      throw error;
    }
  }

  async function flushPageRename() {
    if (pendingPageRenameRef.current) {
      await savePageName(pendingPageRenameRef.current.pageId, pendingPageRenameRef.current.displayName);
    }
  }

  function commitPageName(pageId: string, displayName: string) {
    const currentPage = pages.find((page) => page.id === pageId);
    if (currentPage && currentPage.displayName !== displayName && pageRenameUndoRef.current !== pageId) {
      pushUndo("页面重命名");
      pageRenameUndoRef.current = pageId;
    }
    const nextPages = pages.map((page) => page.id === pageId ? { ...page, displayName } : page);
    setPages(nextPages);
    setSaveState("saving");
    pendingPageRenameRef.current = { pageId, displayName };
    if (pageRenameTimerRef.current) clearTimeout(pageRenameTimerRef.current);
    pageRenameTimerRef.current = setTimeout(() => {
      void savePageName(pageId, displayName).catch(() => undefined);
    }, 500);
  }

  async function savePageName(pageId: string, displayName: string) {
    if (pageRenameTimerRef.current) {
      clearTimeout(pageRenameTimerRef.current);
      pageRenameTimerRef.current = null;
    }
    setSaveState("saving");
    try {
      const result = await renamePage(projectId, pageId, displayName);
      if (pendingPageRenameRef.current?.pageId === pageId && pendingPageRenameRef.current.displayName === displayName) {
        pendingPageRenameRef.current = null;
      }
      setPages((current) => current.map((page) => page.id === pageId ? { ...page, displayName: result.page.displayName } : page));
      setSaveState("saved");
      setStatus("页面名称已保存。");
      pageRenameUndoRef.current = null;
    } catch (error) {
      setSaveState("error");
      setStatus(`页面名称保存失败：${error instanceof Error ? error.message : "unknown error"}`);
      throw error;
    }
  }

  async function exportAssets() {
    try {
      await flushPageRename();
      await saveNow();
      const result = await apiPost<{ ok: true; assetCount: number; url: string }>(`/api/projects/${projectId}/export-assets`, {});
      window.location.href = `${apiBaseUrl}${result.url}`;
      setStatus(`已导出 ${result.assetCount} 个切图。`);
    } catch (error) {
      setStatus(`导出失败：${error instanceof Error ? error.message : "unknown error"}`);
    }
  }

  function fitPage() {
    if (!activePage) return;
    const fitScale = Math.min((stageSize.width - 160) / activePage.width, (stageSize.height - 160) / activePage.height, 1);
    setScale(Math.max(0.08, fitScale));
    setStagePosition({ x: Math.max(40, (stageSize.width - activePage.width * fitScale) / 2), y: Math.max(40, (stageSize.height - activePage.height * fitScale) / 2) });
  }

  function imagePointFromStage(): Point | null {
    const stage = stageRef.current;
    if (!stage || !activePage) return null;
    const pointer = stage.getPointerPosition();
    if (!pointer) return null;
    return {
      x: Math.round((pointer.x - stagePosition.x) / scale),
      y: Math.round((pointer.y - stagePosition.y) / scale)
    };
  }

  function onWheel(event: Konva.KonvaEventObject<WheelEvent>) {
    if (!event.evt.ctrlKey && !event.evt.metaKey) return;
    event.evt.preventDefault();
    const stage = stageRef.current;
    const pointer = stage?.getPointerPosition();
    if (!stage || !pointer) return;
    const oldScale = scale;
    const nextScale = Math.max(0.08, Math.min(4, oldScale * Math.exp(-event.evt.deltaY * 0.0016)));
    const mousePointTo = {
      x: (pointer.x - stagePosition.x) / oldScale,
      y: (pointer.y - stagePosition.y) / oldScale
    };
    setScale(nextScale);
    setStagePosition({
      x: pointer.x - mousePointTo.x * nextScale,
      y: pointer.y - mousePointTo.y * nextScale
    });
  }

  function onMouseDown(event: Konva.KonvaEventObject<MouseEvent>) {
    if (!activePage) return;
    const point = imagePointFromStage();
    if (!point) return;
    if (tool === "pan") {
      setDrag({ type: "pan", startClient: { x: event.evt.clientX, y: event.evt.clientY }, originalPosition: stagePosition });
      return;
    }
    if (tool === "draw") {
      setDrag({ type: "draw", start: point, current: point });
      return;
    }
    const target = event.target;
    const sliceId = target.attrs.sliceId as string | undefined;
    if (sliceId) {
      setActiveSliceId(sliceId);
      return;
    }
    setActiveSliceId(null);
  }

  function onMouseMove(event: Konva.KonvaEventObject<MouseEvent>) {
    if (!drag || !activePage) return;
    if (drag.type === "pan") {
      setStagePosition({
        x: drag.originalPosition.x + event.evt.clientX - drag.startClient.x,
        y: drag.originalPosition.y + event.evt.clientY - drag.startClient.y
      });
      return;
    }
    const point = imagePointFromStage();
    if (!point) return;
    if (drag.type === "draw") {
      setDrag({ ...drag, current: point });
      return;
    }
  }

  function onMouseUp() {
    if (!drag || !activePage) return;
    if (drag.type === "draw") {
      const box = draftToBox(drag.start, drag.current, activePage);
      if (box.width >= 8 && box.height >= 8) addSlice(box);
    }
    setDrag(null);
  }

  function addSlice(bbox: BBox) {
    if (!activePage) return;
    const index = activePage.slices.length + 1;
    const slice: SliceRecord = {
      id: `${activePage.id}__slice_${Date.now().toString(36)}_${index}`,
      projectId,
      pageId: activePage.id,
      sliceIndex: index,
      name: `slice_${String(index).padStart(2, "0")}`,
      kind: "image",
      bbox: normalizeBox(bbox, activePage),
      selected: true
    };
    const nextPages = pages.map((page) => page.id === activePage.id ? { ...page, slices: [...page.slices, slice] } : page);
    setActiveSliceId(slice.id);
    scheduleSave(nextPages, { pushUndo: true, undoLabel: "新建资产" });
  }

  function activateTool(nextTool: ToolMode) {
    setTool((currentTool) => currentTool === nextTool ? currentTool : nextTool);
  }

  function beginSliceEdit(sliceId: string, label = "编辑资产") {
    if (sliceEditUndoRef.current === sliceId) return;
    pushUndo(label);
    sliceEditUndoRef.current = sliceId;
  }

  function commitSlicePatch(sliceId: string, patch: Partial<Pick<SliceRecord, "name" | "bbox">>, undoLabel = "编辑资产", options: { pushUndo?: boolean } = { pushUndo: true }) {
    if (!activePage) return;
    const nextPages = pages.map((page) => page.id === activePage.id ? {
      ...page,
      slices: page.slices.map((slice) => slice.id === sliceId ? { ...slice, ...patch } : slice)
    } : page);
    scheduleSave(nextPages, { pushUndo: options.pushUndo, undoLabel });
  }

  function updateBoxColor(key: keyof typeof defaultBoxColors, value: string) {
    const nextColors = {
      ...boxColors,
      [key]: normalizeColor(value, defaultBoxColors[key])
    };
    setBoxColors(nextColors);
    window.localStorage.setItem(reviewColorStorageKey, JSON.stringify(nextColors));
  }

  function resetBoxColors() {
    setBoxColors(defaultBoxColors);
    window.localStorage.setItem(reviewColorStorageKey, JSON.stringify(defaultBoxColors));
  }

  function deleteActiveSlice(sliceId = activeSliceId) {
    if (!activePage || !sliceId) return;
    const nextPages = pages.map((page) => page.id === activePage.id ? {
      ...page,
      slices: page.slices.filter((slice) => slice.id !== sliceId)
    } : page);
    setActiveSliceId(null);
    scheduleSave(nextPages, { pushUndo: true, undoLabel: "删除资产" });
  }

  function onTransformEnd(slice: SliceRecord, node: Konva.Rect) {
    if (!activePage) return;
    const scaleX = node.scaleX();
    const scaleY = node.scaleY();
    node.scaleX(1);
    node.scaleY(1);
    commitSlicePatch(slice.id, {
      bbox: normalizeBox({
        x: node.x(),
        y: node.y(),
        width: Math.max(1, node.width() * scaleX),
        height: Math.max(1, node.height() * scaleY)
      }, activePage)
    }, "缩放资产");
  }

  async function commitPageOrder(nextPages: WorkbenchPage[], activePageIdAfterOrder = activePageId) {
    if (nextPages.map((page) => page.id).join("|") === pages.map((page) => page.id).join("|")) return;
    setSaveState("saving");
    try {
      await flushPageRename();
      await saveNow();
      pushUndo("调整页面顺序");
      setPages(nextPages);
      const projectDetail = await reorderPages(projectId, nextPages.map((page) => page.id));
      await applyProjectDetail(projectDetail, activePageIdAfterOrder, activeSliceId);
      setSaveState("saved");
      setStatus("页面顺序已保存。");
    } catch (error) {
      setSaveState("error");
      setStatus(`页面排序失败：${error instanceof Error ? error.message : "unknown error"}`);
    }
  }

  function reorderPageList(sourcePageId: string, targetPageId: string, insertAfterTarget: boolean): WorkbenchPage[] {
    if (sourcePageId === targetPageId) return pages;
    const fromIndex = pages.findIndex((page) => page.id === sourcePageId);
    const toIndex = pages.findIndex((page) => page.id === targetPageId);
    if (fromIndex < 0 || toIndex < 0) return pages;
    const nextPages = [...pages];
    const [movedPage] = nextPages.splice(fromIndex, 1);
    const targetIndexAfterRemoval = nextPages.findIndex((page) => page.id === targetPageId);
    nextPages.splice(targetIndexAfterRemoval + (insertAfterTarget ? 1 : 0), 0, movedPage);
    return nextPages;
  }

  function requestReplaceActivePage(fileList: FileList | null) {
    const file = fileList?.[0];
    if (!activePage || !file) return;
    setPageConfirmAction({ type: "replace", pageId: activePage.id, file });
    if (replaceInputRef.current) replaceInputRef.current.value = "";
  }

  async function confirmPageAction() {
    if (!pageConfirmAction) return;
    const targetPage = pages.find((page) => page.id === pageConfirmAction.pageId);
    if (!targetPage) {
      setPageConfirmAction(null);
      return;
    }
    setSaveState("saving");
    try {
      await flushPageRename();
      await saveNow();
      pushUndo(pageConfirmAction.type === "delete" ? "删除页面" : "替换页面", { sourceFileAction: true });
      const projectDetail = pageConfirmAction.type === "delete"
        ? await deletePage(projectId, pageConfirmAction.pageId)
        : await replacePage(projectId, pageConfirmAction.pageId, pageConfirmAction.file);
      await applyProjectDetail(projectDetail, pageConfirmAction.type === "replace" ? pageConfirmAction.pageId : null, null);
      setSaveState("saved");
      setStatus(pageConfirmAction.type === "delete" ? "页面已删除。" : "页面已替换，该页切图已清空。");
      setPageConfirmAction(null);
    } catch (error) {
      setSaveState("error");
      setStatus(`${pageConfirmAction.type === "delete" ? "删除" : "替换"}页面失败：${error instanceof Error ? error.message : "unknown error"}`);
    }
  }

  const draftBox = useMemo(() => {
    if (!drag || drag.type !== "draw" || !activePage) return null;
    return draftToBox(drag.start, drag.current, activePage);
  }, [drag, activePage]);

  return (
    <main className={`reviewShell ${inspectorCollapsed ? "inspectorCollapsed" : ""}`}>
      <header className="reviewTopbar">
        <div className="topbarProject">
          <a className="topbarBack" href="/projects" aria-label="返回项目列表">
            <ArrowLeft aria-hidden="true" />
          </a>
          <div className="projectTitleBlock">
            <strong>{detail?.project.name || "Slice Studio"}</strong>
            <span>{pages.length} pages · {pages.reduce((total, page) => total + page.slices.length, 0)} assets</span>
          </div>
        </div>
        <div className="topbarActions">
          <button className="toolbarButton" type="button" disabled={!undoStack.length} title={undoStack.length ? `撤销：${undoStack[undoStack.length - 1].label}` : "没有可撤销操作"} onClick={() => void restoreUndo()}>
            <RotateCcw aria-hidden="true" />
            <span>撤销</span>
          </button>
          <label className="toolbarButton uploadButton">
            <Upload aria-hidden="true" />
            <span>上传 UI 截图</span>
            <input id="pageUpload" name="pageUpload" type="file" multiple accept="image/*" onChange={(event) => void handleUpload(event.target.files)} />
          </label>
          <div className="zoomGroup" aria-label="缩放控制">
            <button className="zoomButton" type="button" onClick={fitPage}>Fit</button>
            <span className="zoomReadout">{Math.round(scale * 100)}%</span>
            <button className="zoomButton" type="button" onClick={() => setScale(1)}>100%</button>
          </div>
          <button className="toolbarButton exportButton" type="button" disabled={!hasSlices} onClick={() => void exportAssets()}>
            <Download aria-hidden="true" />
            <span>导出 assets.zip</span>
          </button>
          <span className={`saveState ${saveState}`} title={status}>{saveLabel}</span>
        </div>
      </header>

      <aside className="pageRail" aria-label="页面">
        <div className="pageRailHeader">Pages</div>
        <div className="pageRailList">
          {pages.map((page, index) => (
            <div
              key={page.id}
              className={`pageThumbCard ${page.id === activePageId ? "active" : ""} ${page.id === draggingPageId ? "dragging" : ""}`}
              onDragOver={(event) => {
                const sourcePageId = draggingPageId || event.dataTransfer.getData("text/plain");
                if (!sourcePageId || sourcePageId === page.id) return;
                event.preventDefault();
                event.dataTransfer.dropEffect = "move";
              }}
              onDrop={(event) => {
                event.preventDefault();
                const sourcePageId = draggingPageId || event.dataTransfer.getData("text/plain");
                if (!sourcePageId) return;
                const rect = event.currentTarget.getBoundingClientRect();
                const insertAfterTarget = event.clientY > rect.top + rect.height / 2;
                const nextPages = reorderPageList(sourcePageId, page.id, insertAfterTarget);
                setDraggingPageId(null);
                void commitPageOrder(nextPages, sourcePageId);
              }}
            >
              <div
                className="pageDragHandle"
                draggable
                role="button"
                tabIndex={0}
                aria-label={`拖拽调整 P${index + 1} 顺序`}
                title="拖拽调整页面顺序"
                onDragStart={(event) => {
                  setDraggingPageId(page.id);
                  event.dataTransfer.effectAllowed = "move";
                  event.dataTransfer.setData("text/plain", page.id);
                }}
                onDragEnd={() => setDraggingPageId(null)}
              >
                <GripHorizontal aria-hidden="true" />
              </div>
              <button type="button" className="pageThumbButton" title={page.originalName} onClick={() => {
                setActivePageId(page.id);
                setActiveSliceId(null);
              }}>
                <span className="pageThumbImage">
                  <img src={`${apiBaseUrl}${page.sourceUrl}`} alt="" />
                </span>
                <span className="pageThumbMeta">P{index + 1}</span>
                <span className="pageThumbName">{page.displayName || page.originalName}</span>
                <span className="pageThumbCount">{page.slices.length}</span>
              </button>
            </div>
          ))}
          {!pages.length && (
            <div className="pageRailEmpty">
              <Images aria-hidden="true" />
              <span>无页面</span>
            </div>
          )}
        </div>
      </aside>

      <section className="stageArea">
        <nav className="floatingTools" aria-label="切图工具">
          <button className={tool === "select" ? "active" : ""} type="button" title="选择（V）" aria-label="选择工具，快捷键 V" onPointerDown={(event) => {
            event.preventDefault();
            activateTool("select");
          }} onClick={() => activateTool("select")}>
            <MousePointer2 aria-hidden="true" />
          </button>
          <button className={tool === "draw" ? "active" : ""} type="button" title="画框（B）" aria-label="画框工具，快捷键 B" onPointerDown={(event) => {
            event.preventDefault();
            activateTool("draw");
          }} onClick={() => activateTool("draw")}>
            <Square aria-hidden="true" />
          </button>
          <button className={tool === "pan" ? "active" : ""} type="button" title="移动画布（H）" aria-label="移动画布工具，快捷键 H" onPointerDown={(event) => {
            event.preventDefault();
            activateTool("pan");
          }} onClick={() => activateTool("pan")}>
            <Hand aria-hidden="true" />
          </button>
        </nav>
        <div ref={stageWrapRef} className="stageWrap">
          {!activePage && <div className="canvasHint">上传 UI 截图开始切图</div>}
          {activePage && (
            <Stage
              ref={stageRef}
              width={stageSize.width}
              height={stageSize.height}
              onWheel={onWheel}
              onMouseDown={onMouseDown}
              onMouseMove={onMouseMove}
              onMouseUp={onMouseUp}
              className={`konvaStage tool-${tool}`}
            >
              <Layer x={stagePosition.x} y={stagePosition.y} scaleX={scale} scaleY={scale}>
                {activePage.image && <KonvaImage image={activePage.image} width={activePage.width} height={activePage.height} listening={false} />}
                {activePage.slices.map((slice, index) => {
                  const isActive = slice.id === activeSliceId;
                  return (
                    <Rect
                      key={slice.id}
                      ref={isActive ? activeRectRef : undefined}
                      sliceId={slice.id}
                      x={slice.bbox.x}
                      y={slice.bbox.y}
                      width={slice.bbox.width}
                      height={slice.bbox.height}
                      stroke={isActive ? boxColors.active : boxColors.slice}
                      strokeWidth={isActive ? 2 : 1.4}
                      fill={colorWithAlpha(boxColors.slice, tool === "draw" ? 0.02 : 0.08)}
                      draggable={tool === "select"}
                      listening={tool === "select"}
                      onDragEnd={(event) => {
                        commitSlicePatch(slice.id, { bbox: normalizeBox({ ...slice.bbox, x: event.target.x(), y: event.target.y() }, activePage) }, "移动资产");
                      }}
                      onTransformEnd={(event) => onTransformEnd(slice, event.target as Konva.Rect)}
                    />
                  );
                })}
                {tool === "select" && activeSlice && activeRectRef.current && (
                  <Transformer
                    ref={transformerRef}
                    rotateEnabled={false}
                    enabledAnchors={transformerAnchors}
                    boundBoxFunc={(_, newBox) => ({
                      ...newBox,
                      width: Math.max(8, newBox.width),
                      height: Math.max(8, newBox.height)
                    })}
                  />
                )}
                {tool === "select" && activeSlice && (
                  <Text x={activeSlice.bbox.x} y={activeSlice.bbox.y - 18} text={`#${activePage.slices.findIndex((slice) => slice.id === activeSlice.id) + 1}`} fill="#fff" fontSize={12} padding={4} listening={false} />
                )}
                {draftBox && (
                  <>
                    <Rect {...draftBox} stroke="#000" strokeWidth={4} dash={[8, 4]} listening={false} />
                    <Rect {...draftBox} stroke="#fff" strokeWidth={2} dash={[8, 4]} listening={false} />
                  </>
                )}
              </Layer>
            </Stage>
          )}
        </div>
      </section>

      <aside className="assetInspector" aria-label="资产检查器">
        <button className="inspectorToggle" type="button" aria-label={inspectorCollapsed ? "展开资产检查器" : "折叠资产检查器"} title={inspectorCollapsed ? "展开资产检查器" : "折叠资产检查器"} onClick={() => setInspectorCollapsed((value) => !value)}>
          {inspectorCollapsed ? <PanelRightOpen aria-hidden="true" /> : <PanelRightClose aria-hidden="true" />}
        </button>
        {!inspectorCollapsed && (
          <div className="inspectorInner">
            <header className="inspectorHeader">
              <h2>Assets</h2>
              <span>{activePageAssetCount} assets</span>
            </header>
            <section className="pageInfoPanel">
              <strong>{activePage ? `P${pageIndex + 1}` : "No page"}</strong>
              {activePage ? (
                <label className="pageNameField">
                  <span>页面名称</span>
                  <input
                    name={`pageName-${activePage.id}`}
                    aria-label="页面名称"
                    placeholder={`Page ${pageIndex + 1}`}
                    value={activePage.displayName}
                    onChange={(event) => commitPageName(activePage.id, event.target.value)}
                  />
                </label>
              ) : null}
              <span>{activePage ? `${activePage.width}x${activePage.height} · ${activePage.originalName}` : "上传 UI 截图后开始切图"}</span>
              {activePage ? (
                <div className="pageActionGrid">
                  <button type="button" onClick={() => replaceInputRef.current?.click()}>
                    <Upload aria-hidden="true" />
                    替换
                  </button>
                  <button type="button" className="dangerButton" onClick={() => setPageConfirmAction({ type: "delete", pageId: activePage.id })}>
                    <Trash2 aria-hidden="true" />
                    删除
                  </button>
                </div>
              ) : null}
            </section>
            <section className="boxColorPanel">
              <div className="boxColorHeader">
                <strong>框颜色</strong>
                <button type="button" onClick={resetBoxColors}>重置</button>
              </div>
              <label>
                <span>普通框</span>
                <input type="color" value={boxColors.slice} onChange={(event) => updateBoxColor("slice", event.target.value)} aria-label="普通框颜色" />
              </label>
              <label>
                <span>选中框</span>
                <input type="color" value={boxColors.active} onChange={(event) => updateBoxColor("active", event.target.value)} aria-label="选中框颜色" />
              </label>
            </section>
            {activeSlice ? (
              <section className="activeAssetPanel">
                <div className="activeAssetHeader">
                  <div>
                    <span>Active asset</span>
                    <strong>{activeSlice.name || "Untitled"}</strong>
                  </div>
                  <button className="assetDangerButton" type="button" aria-label="删除当前资产" title="删除当前资产" onClick={() => deleteActiveSlice(activeSlice.id)}>
                    <Trash2 aria-hidden="true" />
                  </button>
                </div>
                <div className="compactFields">
                  <label className="nameField">
                    <span>名称</span>
                    <input
                      name={`activeSliceName-${activeSlice.id}`}
                      aria-label="资产名称"
                      value={activeSlice.name}
                      onFocus={() => beginSliceEdit(activeSlice.id, "编辑资产")}
                      onBlur={() => {
                        sliceEditUndoRef.current = null;
                      }}
                      onChange={(event) => commitSlicePatch(activeSlice.id, { name: event.target.value }, "编辑资产", { pushUndo: false })}
                    />
                  </label>
                </div>
                <div className="bboxGrid">
                  <span>x {activeSlice.bbox.x}</span>
                  <span>y {activeSlice.bbox.y}</span>
                  <span>w {activeSlice.bbox.width}</span>
                  <span>h {activeSlice.bbox.height}</span>
                </div>
              </section>
            ) : (
              <section className="inspectorSummary">
                <span>{activePage ? `${activePageAssetCount} assets on this page · ${totalAssets} total` : "顶部按钮可上传 1..N 张图片"}</span>
                {activePageAssetCount === 0 && (
                  <span>{activePage ? "使用画框工具创建资产，选择工具调整资产。" : "画布保持纯黑，不显示白色空态卡片。"}</span>
                )}
              </section>
            )}
            <div className="assetList">
              {activePage?.slices.map((slice, index) => (
                <div
                  key={slice.id}
                  className={`assetItem ${slice.id === activeSliceId ? "active" : ""}`}
                  onClick={() => setActiveSliceId(slice.id)}
                >
                  <span className="assetIndex">#{index + 1}</span>
                  <span className="assetFields">
                    <input
                      name={`sliceName-${slice.id}`}
                      aria-label="资产名称"
                      value={slice.name}
                      onFocus={() => {
                        setActiveSliceId(slice.id);
                        beginSliceEdit(slice.id, "编辑资产");
                      }}
                      onBlur={() => {
                        sliceEditUndoRef.current = null;
                      }}
                      onClick={(event) => event.stopPropagation()}
                      onChange={(event) => commitSlicePatch(slice.id, { name: event.target.value }, "编辑资产", { pushUndo: false })}
                    />
                  </span>
                  <button className="assetItemDelete" type="button" aria-label={`删除 ${slice.name}`} title="删除资产" onClick={(event) => {
                    event.stopPropagation();
                    deleteActiveSlice(slice.id);
                  }}>
                    <Trash2 aria-hidden="true" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </aside>
      <input ref={replaceInputRef} className="hiddenFileInput" type="file" accept="image/*" onChange={(event) => requestReplaceActivePage(event.target.files)} />
      {pageConfirmAction ? (
        <div className="modalBackdrop" role="presentation" onMouseDown={() => setPageConfirmAction(null)}>
          <section
            className="confirmDialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="page-action-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <button type="button" className="dialogCloseButton" aria-label="关闭" onClick={() => setPageConfirmAction(null)}>
              <X aria-hidden="true" />
            </button>
            <div className={`dialogIcon ${pageConfirmAction.type === "delete" ? "danger" : "primary"}`}>
              {pageConfirmAction.type === "delete" ? <Trash2 aria-hidden="true" /> : <Upload aria-hidden="true" />}
            </div>
            <div className="dialogText">
              <h2 id="page-action-title">{pageConfirmAction.type === "delete" ? "删除当前页面？" : "替换当前页面？"}</h2>
              <p>
                {pageConfirmAction.type === "delete"
                  ? "该页面的原图和切图记录都会删除，剩余页面会重新生成 P1/P2 顺序。"
                  : `将使用“${pageConfirmAction.file.name}”替换当前页面原图，并清空该页已有切图。`}
              </p>
            </div>
            <div className="dialogActions">
              <button type="button" onClick={() => setPageConfirmAction(null)}>取消</button>
              <button type="button" className={pageConfirmAction.type === "delete" ? "dangerConfirmButton" : "primaryConfirmButton"} onClick={() => void confirmPageAction()}>
                {pageConfirmAction.type === "delete" ? "确认删除" : "确认替换"}
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </main>
  );
}

function normalizeColor(value: unknown, fallback: string): string {
  return typeof value === "string" && /^#[0-9a-fA-F]{6}$/.test(value) ? value : fallback;
}

function colorWithAlpha(hex: string, alpha: number): string {
  const normalized = normalizeColor(hex, defaultBoxColors.slice);
  const red = Number.parseInt(normalized.slice(1, 3), 16);
  const green = Number.parseInt(normalized.slice(3, 5), 16);
  const blue = Number.parseInt(normalized.slice(5, 7), 16);
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

function serializeSlices(pages: WorkbenchPage[], activePageId: string | null) {
  return {
    activePageId,
    pages: pages.map((page) => ({
      pageId: page.id,
      slices: page.slices.map((slice) => ({
        id: slice.id,
        name: slice.name,
        kind: slice.kind,
        bbox: slice.bbox,
        selected: true as const
      }))
    }))
  };
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("image load failed"));
    image.src = src;
  });
}
