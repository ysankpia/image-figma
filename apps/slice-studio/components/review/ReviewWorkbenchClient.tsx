"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, Download, Hand, Images, MousePointer2, PanelRightClose, PanelRightOpen, Square, Trash2, Upload } from "lucide-react";
import { Image as KonvaImage, Layer, Rect, Stage, Text, Transformer } from "react-konva";
import type Konva from "konva";
import { apiBaseUrl, apiGet, apiPost, saveSlices, uploadPages } from "@/components/api";
import { draftToBox, moveBox, normalizeBox, resizeBox, type ResizeHandle } from "@/shared/bbox";
import type { BBox, PageRecord, ProjectDetail, SaveState, SliceRecord, ToolMode } from "@/shared/types";

type WorkbenchPage = PageRecord & {
  slices: SliceRecord[];
  image: HTMLImageElement | null;
};

type DragState =
  | { type: "draw"; start: Point; current: Point }
  | { type: "move"; sliceId: string; start: Point; original: BBox }
  | { type: "resize"; sliceId: string; handle: ResizeHandle; start: Point; original: BBox }
  | { type: "pan"; startClient: Point; originalPosition: Point };

type Point = { x: number; y: number };

const transformerAnchors = ["top-left", "top-center", "top-right", "middle-right", "bottom-right", "bottom-center", "bottom-left", "middle-left"];

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
  const stageWrapRef = useRef<HTMLDivElement | null>(null);
  const stageRef = useRef<Konva.Stage | null>(null);
  const transformerRef = useRef<Konva.Transformer | null>(null);
  const activeRectRef = useRef<Konva.Rect | null>(null);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const activePage = pages.find((page) => page.id === activePageId) || null;
  const activeSlice = activePage?.slices.find((slice) => slice.id === activeSliceId) || null;
  const hasSlices = pages.some((page) => page.slices.length > 0);

  const loadProject = useCallback(async () => {
    const projectDetail = await apiGet<ProjectDetail>(`/api/projects/${projectId}`);
    const hydratedPages = await Promise.all(projectDetail.pages.map(hydratePage));
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
      if (target && ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName)) return;
      if (event.key.toLowerCase() === "v") setTool("select");
      if (event.key.toLowerCase() === "b") setTool("draw");
      if (event.key.toLowerCase() === "h") setTool("pan");
      if (event.key === "Delete" || event.key === "Backspace") {
        event.preventDefault();
        deleteActiveSlice();
      }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        void saveNow();
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

  function scheduleSave(nextPages: WorkbenchPage[]) {
    setPages(nextPages);
    setSaveState("saving");
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      void saveNow(nextPages);
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
    }
  }

  async function exportAssets() {
    try {
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
      const slice = activePage.slices.find((item) => item.id === sliceId);
      if (slice) setDrag({ type: "move", sliceId, start: point, original: { ...slice.bbox } });
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
    const dx = point.x - drag.start.x;
    const dy = point.y - drag.start.y;
    updateSliceBox(activePage.id, drag.sliceId, drag.type === "move"
      ? moveBox(drag.original, dx, dy, activePage)
      : resizeBox(drag.original, drag.handle, dx, dy, activePage));
  }

  function onMouseUp() {
    if (!drag || !activePage) return;
    if (drag.type === "draw") {
      const box = draftToBox(drag.start, drag.current, activePage);
      if (box.width >= 8 && box.height >= 8) addSlice(box);
    } else if (drag.type === "move" || drag.type === "resize") {
      scheduleSave(pages);
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
    scheduleSave(nextPages);
  }

  function activateTool(nextTool: ToolMode) {
    setTool((currentTool) => currentTool === nextTool ? currentTool : nextTool);
  }

  function updateSliceBox(pageId: string, sliceId: string, bbox: BBox) {
    setPages((current) => current.map((page) => page.id === pageId ? {
      ...page,
      slices: page.slices.map((slice) => slice.id === sliceId ? { ...slice, bbox } : slice)
    } : page));
  }

  function commitSlicePatch(sliceId: string, patch: Partial<Pick<SliceRecord, "name" | "kind" | "bbox">>) {
    if (!activePage) return;
    const nextPages = pages.map((page) => page.id === activePage.id ? {
      ...page,
      slices: page.slices.map((slice) => slice.id === sliceId ? { ...slice, ...patch } : slice)
    } : page);
    scheduleSave(nextPages);
  }

  function deleteActiveSlice(sliceId = activeSliceId) {
    if (!activePage || !sliceId) return;
    const nextPages = pages.map((page) => page.id === activePage.id ? {
      ...page,
      slices: page.slices.filter((slice) => slice.id !== sliceId)
    } : page);
    setActiveSliceId(null);
    scheduleSave(nextPages);
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
    });
  }

  const draftBox = useMemo(() => {
    if (!drag || drag.type !== "draw" || !activePage) return null;
    return draftToBox(drag.start, drag.current, activePage);
  }, [drag, activePage]);
  const pageIndex = activePage ? pages.findIndex((page) => page.id === activePage.id) : -1;

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
          <label className="toolbarButton uploadButton">
            <Upload aria-hidden="true" />
            <span>上传 UI 截图</span>
            <input id="pageUpload" name="pageUpload" type="file" multiple accept="image/*" onChange={(event) => void handleUpload(event.target.files)} />
          </label>
          <button className="toolbarButton" type="button" onClick={fitPage}>Fit</button>
          <button className="toolbarButton" type="button" onClick={() => setScale(1)}>100%</button>
          <span className="zoomReadout">{Math.round(scale * 100)}%</span>
          <button className="toolbarButton exportButton" type="button" disabled={!hasSlices} onClick={() => void exportAssets()}>
            <Download aria-hidden="true" />
            <span>导出 assets.zip</span>
          </button>
          <span className={`saveState ${saveState}`}>{status}</span>
        </div>
      </header>

      <aside className="pageRail" aria-label="页面">
        <div className="pageRailHeader">Pages</div>
        <div className="pageRailList">
          {pages.map((page, index) => (
            <button key={page.id} type="button" className={`pageThumbButton ${page.id === activePageId ? "active" : ""}`} title={page.originalName} onClick={() => {
              setActivePageId(page.id);
              setActiveSliceId(null);
            }}>
              <span className="pageThumbImage">
                <img src={`${apiBaseUrl}${page.sourceUrl}`} alt="" />
              </span>
              <span className="pageThumbMeta">P{index + 1}</span>
              <span className="pageThumbCount">{page.slices.length}</span>
            </button>
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
          <button type="button" disabled={!activeSlice} title="删除选中资产" aria-label="删除选中资产" onClick={() => deleteActiveSlice()}>
            <Trash2 aria-hidden="true" />
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
                      stroke={isActive ? "#ff2d55" : "#0066cc"}
                      strokeWidth={isActive ? 2 : 1.4}
                      fill={tool === "draw" ? "rgba(0,102,204,0.02)" : "rgba(0,102,204,0.08)"}
                      draggable={tool === "select"}
                      listening={tool === "select"}
                      onDragEnd={(event) => {
                        commitSlicePatch(slice.id, { bbox: normalizeBox({ ...slice.bbox, x: event.target.x(), y: event.target.y() }, activePage) });
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
              <span>{activePage?.slices.length || 0} selected</span>
            </header>
            {activeSlice ? (
              <section className="activeAssetPanel">
                <div className="fieldStack">
                  <label>
                    <span>名称</span>
                    <input name={`activeSliceName-${activeSlice.id}`} aria-label="资产名称" value={activeSlice.name} onChange={(event) => commitSlicePatch(activeSlice.id, { name: event.target.value })} />
                  </label>
                  <label>
                    <span>类型</span>
                    <select name={`activeSliceKind-${activeSlice.id}`} aria-label="资产类型" value={activeSlice.kind} onChange={(event) => commitSlicePatch(activeSlice.id, { kind: event.target.value === "icon" ? "icon" : "image" })}>
                      <option value="image">image</option>
                      <option value="icon">icon</option>
                    </select>
                  </label>
                </div>
                <div className="bboxGrid">
                  <span>x {activeSlice.bbox.x}</span>
                  <span>y {activeSlice.bbox.y}</span>
                  <span>w {activeSlice.bbox.width}</span>
                  <span>h {activeSlice.bbox.height}</span>
                </div>
                <button className="dangerButton" type="button" onClick={() => deleteActiveSlice(activeSlice.id)}>
                  删除选中资产
                </button>
              </section>
            ) : (
              <section className="inspectorSummary">
                <strong>{activePage ? `Page ${pageIndex + 1}` : "No page"}</strong>
                <span>{activePage ? `${activePage.width}x${activePage.height}` : "上传 UI 截图后开始切图"}</span>
                <span>{activePage ? `${activePage.slices.length} selected assets` : "顶部按钮可上传 1..N 张图片"}</span>
                <span>{activePage ? "使用画框工具创建资产，选择工具调整资产。" : "画布保持纯黑，不显示白色空态卡片。"}</span>
              </section>
            )}
            <div className="assetList">
              {activePage?.slices.map((slice) => (
                <div key={slice.id} className={`assetItem ${slice.id === activeSliceId ? "active" : ""}`} onClick={() => setActiveSliceId(slice.id)}>
                  <input name={`sliceName-${slice.id}`} aria-label="资产名称" value={slice.name} onChange={(event) => commitSlicePatch(slice.id, { name: event.target.value })} />
                  <select name={`sliceKind-${slice.id}`} aria-label="资产类型" value={slice.kind} onChange={(event) => commitSlicePatch(slice.id, { kind: event.target.value === "icon" ? "icon" : "image" })}>
                    <option value="image">image</option>
                    <option value="icon">icon</option>
                  </select>
                  <span>{slice.bbox.width}x{slice.bbox.height} · x{slice.bbox.x} y{slice.bbox.y}</span>
                  <button type="button" onClick={(event) => {
                    event.stopPropagation();
                    deleteActiveSlice(slice.id);
                  }}>删除</button>
                </div>
              ))}
            </div>
          </div>
        )}
      </aside>
    </main>
  );
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
