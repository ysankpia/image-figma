import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Group, Image as KonvaImage, Layer, Rect, Stage, Text } from 'react-konva';
import type Konva from 'konva';
import { apiPost, apiPut, getCandidates, getManual, getProject, getReviewState, listProjects } from './api';
import { candidateAt, handlesFor, hitHandle, moveBox, resizeBox, sliceAt } from './geometry';
import type { BBox, Candidate, CandidatesDoc, HandleName, ManualDoc, ManualPage, ManualSlice, PageDoc, ProjectSummary, ReviewState, ToolMode } from './types';
import './style.css';

type DragState =
  | { type: 'pan'; start: { x: number; y: number }; viewport: { x: number; y: number; scale: number } }
  | { type: 'draw'; start: { x: number; y: number }; pageId: string; draft: BBox }
  | { type: 'move'; start: { x: number; y: number }; pageId: string; sliceId: string; original: BBox }
  | { type: 'resize'; start: { x: number; y: number }; pageId: string; sliceId: string; original: BBox; handle: HandleName };

type PageLayout = PageDoc & { offsetX: number; offsetY: number };

const PAGE_GAP = 120;
const DEFAULT_COLS = 3;

export default function App() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [project, setProject] = useState<ProjectSummary | null>(null);
  const [candidates, setCandidates] = useState<CandidatesDoc | null>(null);
  const [manual, setManual] = useState<ManualDoc | null>(null);
  const [reviewState, setReviewState] = useState<ReviewState | null>(null);
  const [images, setImages] = useState<Record<string, HTMLImageElement>>({});
  const [activePageId, setActivePageId] = useState<string | null>(null);
  const [activeSliceId, setActiveSliceId] = useState<string | null>(null);
  const [tool, setTool] = useState<ToolMode>('select');
  const [drag, setDrag] = useState<DragState | null>(null);
  const [projectName, setProjectName] = useState('Pencil Handoff Project');
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState('');
  const [stageSize, setStageSize] = useState({ width: window.innerWidth - 520, height: window.innerHeight - 64 });
  const stageRef = useRef<Konva.Stage>(null);

  const projectIdFromUrl = new URLSearchParams(window.location.search).get('projectId');

  useEffect(() => {
    void refreshProjects();
  }, []);

  useEffect(() => {
    if (projectIdFromUrl) void openProject(projectIdFromUrl);
  }, [projectIdFromUrl]);

  useEffect(() => {
    const onResize = () => setStageSize({ width: Math.max(420, window.innerWidth - 520), height: Math.max(420, window.innerHeight - 64) });
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return;
      if (event.key === 'v' || event.key === 'V') setTool('select');
      if (event.key === 'b' || event.key === 'B') setTool('draw');
      if (event.key === 'h' || event.key === 'H') setTool('pan');
      if ((event.key === 'Delete' || event.key === 'Backspace') && activeSliceId) {
        event.preventDefault();
        deleteSlice(activeSliceId);
      }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's') {
        event.preventDefault();
        void saveAll();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [activeSliceId, manual, reviewState]);

  const pages = candidates?.pages ?? [];
  const layouts = useMemo(() => computeLayouts(pages), [pages]);
  const colors = reviewState?.filters.colors ?? {};
  const viewport = reviewState?.viewport ?? { x: 40, y: 40, scale: 0.5 };

  useEffect(() => {
    if (!project || !candidates) return;
    for (const page of candidates.pages) {
      if (images[page.pageId]) continue;
      const image = new window.Image();
      image.onload = () => setImages((current) => ({ ...current, [page.pageId]: image }));
      image.src = `/api/handoff-projects/${project.projectId}/source/${page.pageId}`;
    }
  }, [project, candidates, images]);

  const refreshProjects = async () => {
    setProjects(await listProjects());
  };

  const openProject = async (projectId: string) => {
    const [summary, candidateDoc, manualDoc, stateDoc] = await Promise.all([
      getProject(projectId),
      getCandidates(projectId),
      getManual(projectId),
      getReviewState(projectId),
    ]);
    setProject(summary);
    setCandidates(candidateDoc);
    setManual(manualDoc);
    setReviewState(stateDoc);
    setActivePageId(stateDoc.activePageId ?? candidateDoc.pages[0]?.pageId ?? null);
    setActiveSliceId(null);
    setMessage(`已打开 ${summary.projectName}`);
  };

  const createProject = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const input = event.currentTarget.elements.namedItem('files') as HTMLInputElement;
    if (!input.files?.length) return;
    const form = new FormData();
    form.set('projectName', projectName);
    form.set('includeOcr', 'true');
    form.set('includeBasicElements', 'true');
    for (const file of Array.from(input.files)) form.append('files[]', file, file.name);
    setUploading(true);
    try {
      const created = await apiPost<ProjectSummary>('/api/handoff-projects', form);
      await refreshProjects();
      await openProject(created.projectId);
      window.history.replaceState(null, '', `/studio/?projectId=${created.projectId}`);
    } finally {
      setUploading(false);
    }
  };

  const saveAll = async () => {
    if (!project || !manual || !reviewState) return;
    const savedManual = await apiPut<{ selectedSliceCount: number; manualSlices: ManualDoc }>(`/api/handoff-projects/${project.projectId}/manual-slices`, manual);
    const savedState = await apiPut<{ reviewState: ReviewState }>(`/api/handoff-projects/${project.projectId}/review-state`, reviewState);
    setManual(savedManual.manualSlices);
    setReviewState(savedState.reviewState);
    setMessage(`已保存 ${savedManual.selectedSliceCount} 个资产`);
  };

  const exportProject = async () => {
    if (!project) return;
    await saveAll();
    const manifest = await apiPost<{ projectZipUrl: string; assetsZipUrl: string }>(`/api/handoff-projects/${project.projectId}/export`);
    setMessage('导出完成');
    window.open(manifest.assetsZipUrl, '_blank');
    window.open(manifest.projectZipUrl, '_blank');
  };

  const setViewport = (next: { x: number; y: number; scale: number }) => {
    setReviewState((current) => (current ? { ...current, viewport: next } : current));
  };

  const pageManual = (pageId: string): ManualPage | undefined => manual?.pages.find((page) => page.pageId === pageId);
  const pageHiddenIds = (pageId: string): Set<string> => {
    const page = reviewState?.pages.find((item) => item.pageId === pageId);
    return new Set([...(page?.hiddenCandidateIds ?? []), ...(page?.rejectedCandidateIds ?? [])]);
  };

  const updateManualPage = (pageId: string, updater: (page: ManualPage) => ManualPage) => {
    setManual((current) => {
      if (!current) return current;
      return { ...current, pages: current.pages.map((page) => (page.pageId === pageId ? updater(page) : page)) };
    });
  };

  const addCandidateSlice = (page: PageLayout, candidate: Candidate) => {
    const kind = candidate.kind === 'icon' ? 'icon' : candidate.kind === 'image' ? 'image' : 'basic';
    updateManualPage(page.pageId, (manualPage) => {
      const id = `${page.pageId}__slice_${manualPage.slices.length + 1}`.replace(/[^0-9A-Za-z_-]/g, '_');
      const slice: ManualSlice = {
        id,
        pageId: page.pageId,
        name: `slice_${manualPage.slices.length + 1}`,
        displayName: `slice_${manualPage.slices.length + 1}`,
        kind,
        bbox: candidate.bbox,
        selected: true,
        source: 'candidate_confirmed',
        candidateIds: [candidate.id],
        tags: [],
      };
      setActiveSliceId(id);
      return { ...manualPage, slices: [...manualPage.slices, slice] };
    });
  };

  const addManualSlice = (page: PageLayout, bbox: BBox) => {
    updateManualPage(page.pageId, (manualPage) => {
      const id = `${page.pageId}__slice_${manualPage.slices.length + 1}`.replace(/[^0-9A-Za-z_-]/g, '_');
      const slice: ManualSlice = {
        id,
        pageId: page.pageId,
        name: `slice_${manualPage.slices.length + 1}`,
        displayName: `slice_${manualPage.slices.length + 1}`,
        kind: 'image',
        bbox,
        selected: true,
        source: 'manual',
        candidateIds: [],
        tags: [],
      };
      setActiveSliceId(id);
      return { ...manualPage, slices: [...manualPage.slices, slice] };
    });
  };

  const hideCandidate = (pageId: string, candidateId: string) => {
    setReviewState((current) => {
      if (!current) return current;
      return {
        ...current,
        pages: current.pages.map((page) =>
          page.pageId === pageId
            ? { ...page, hiddenCandidateIds: Array.from(new Set([...page.hiddenCandidateIds, candidateId])), rejectedCandidateIds: Array.from(new Set([...page.rejectedCandidateIds, candidateId])) }
            : page,
        ),
      };
    });
  };

  const restoreHidden = (pageId: string) => {
    setReviewState((current) => {
      if (!current) return current;
      return { ...current, pages: current.pages.map((page) => (page.pageId === pageId ? { ...page, hiddenCandidateIds: [], rejectedCandidateIds: [] } : page)) };
    });
  };

  const deleteSlice = (sliceId: string) => {
    setManual((current) => {
      if (!current) return current;
      return { ...current, pages: current.pages.map((page) => ({ ...page, slices: page.slices.filter((slice) => slice.id !== sliceId) })) };
    });
    setActiveSliceId(null);
  };

  const stagePoint = (): { x: number; y: number } | null => {
    const stage = stageRef.current;
    const pointer = stage?.getPointerPosition();
    if (!pointer) return null;
    return { x: (pointer.x - viewport.x) / viewport.scale, y: (pointer.y - viewport.y) / viewport.scale };
  };

  const locatePage = (point: { x: number; y: number }): { page: PageLayout; local: { x: number; y: number } } | null => {
    for (const page of layouts) {
      if (point.x >= page.offsetX && point.y >= page.offsetY && point.x <= page.offsetX + page.width && point.y <= page.offsetY + page.height) {
        return { page, local: { x: point.x - page.offsetX, y: point.y - page.offsetY } };
      }
    }
    return null;
  };

  const onMouseDown = (event: Konva.KonvaEventObject<MouseEvent>) => {
    const point = stagePoint();
    if (!point || !manual || !reviewState) return;
    if (event.evt.button === 1 || tool === 'pan') {
      setDrag({ type: 'pan', start: { x: event.evt.clientX, y: event.evt.clientY }, viewport });
      return;
    }
    const located = locatePage(point);
    if (!located) {
      setActiveSliceId(null);
      return;
    }
    setActivePageId(located.page.pageId);
    setReviewState((current) => (current ? { ...current, activePageId: located.page.pageId } : current));
    const manualPage = pageManual(located.page.pageId);
    if (!manualPage) return;
    const activeSlice = manualPage.slices.find((slice) => slice.id === activeSliceId);
    const handle = hitHandle(activeSlice, located.local);
    if (handle) {
      setDrag({ type: 'resize', start: located.local, pageId: located.page.pageId, sliceId: activeSlice!.id, original: activeSlice!.bbox, handle });
      return;
    }
    if (tool === 'draw') {
      setDrag({ type: 'draw', start: located.local, pageId: located.page.pageId, draft: { x: located.local.x, y: located.local.y, width: 0, height: 0 } });
      return;
    }
    const hitSlice = sliceAt(manualPage.slices, located.local);
    if (hitSlice) {
      setActiveSliceId(hitSlice.id);
      setDrag({ type: 'move', start: located.local, pageId: located.page.pageId, sliceId: hitSlice.id, original: hitSlice.bbox });
      return;
    }
    const hidden = pageHiddenIds(located.page.pageId);
    const candidate = candidateAt(located.page.candidates ?? [], hidden, located.local);
    if (candidate) {
      if (event.evt.altKey || event.evt.button === 2) hideCandidate(located.page.pageId, candidate.id);
      else addCandidateSlice(located.page, candidate);
    } else {
      setActiveSliceId(null);
    }
  };

  const onMouseMove = () => {
    if (!drag || !manual || !reviewState) return;
    if (drag.type === 'pan') {
      const stage = stageRef.current;
      const pointer = stage?.getPointerPosition();
      if (!pointer) return;
      setViewport({ ...drag.viewport, x: drag.viewport.x + pointer.x - drag.start.x, y: drag.viewport.y + pointer.y - drag.start.y });
      return;
    }
    const point = stagePoint();
    if (!point) return;
    const layout = layouts.find((page) => page.pageId === drag.pageId);
    if (!layout) return;
    const local = { x: point.x - layout.offsetX, y: point.y - layout.offsetY };
    if (drag.type === 'draw') {
      const x = Math.min(drag.start.x, local.x);
      const y = Math.min(drag.start.y, local.y);
      const right = Math.max(drag.start.x, local.x);
      const bottom = Math.max(drag.start.y, local.y);
      setDrag({ ...drag, draft: { x: Math.round(x), y: Math.round(y), width: Math.round(right - x), height: Math.round(bottom - y) } });
    } else if (drag.type === 'move') {
      const dx = local.x - drag.start.x;
      const dy = local.y - drag.start.y;
      updateSliceBox(drag.pageId, drag.sliceId, moveBox(drag.original, dx, dy, layout));
    } else if (drag.type === 'resize') {
      const dx = local.x - drag.start.x;
      const dy = local.y - drag.start.y;
      updateSliceBox(drag.pageId, drag.sliceId, resizeBox(drag.original, drag.handle, dx, dy, layout));
    }
  };

  const onMouseUp = () => {
    if (drag?.type === 'draw') {
      const layout = layouts.find((page) => page.pageId === drag.pageId);
      if (layout && drag.draft.width >= 4 && drag.draft.height >= 4) addManualSlice(layout, drag.draft);
    }
    setDrag(null);
  };

  const updateSliceBox = (pageId: string, sliceId: string, bbox: BBox) => {
    updateManualPage(pageId, (page) => ({ ...page, slices: page.slices.map((slice) => (slice.id === sliceId ? { ...slice, bbox } : slice)) }));
  };

  const activePage = activePageId ? layouts.find((page) => page.pageId === activePageId) : layouts[0];
  const selectedSlices = manual?.pages.flatMap((page) => page.slices.map((slice) => ({ ...slice, pageId: page.pageId }))) ?? [];

  return (
    <div className="appShell">
      <aside className="sidebar">
        <h1>Pencil Handoff Studio</h1>
        <form onSubmit={createProject} className="uploadForm">
          <input
            id="projectName"
            name="projectName"
            aria-label="项目名"
            value={projectName}
            onChange={(event) => setProjectName(event.target.value)}
          />
          <input name="files" type="file" accept="image/*" multiple />
          <button type="submit" disabled={uploading}>{uploading ? '上传中' : '创建项目'}</button>
        </form>
        <div className="projectList">
          {projects.map((item) => (
            <button key={item.projectId} className={project?.projectId === item.projectId ? 'active' : ''} onClick={() => openProject(item.projectId)}>
              <strong>{item.projectName}</strong>
              <span>{item.pageCount} 页 · {item.selectedSliceCount} 个资产</span>
            </button>
          ))}
        </div>
      </aside>

      <main className="main">
        <header className="toolbar">
          <button className={tool === 'select' ? 'active' : ''} onClick={() => setTool('select')}>选择 V</button>
          <button className={tool === 'draw' ? 'active' : ''} onClick={() => setTool('draw')}>画框 B</button>
          <button className={tool === 'pan' ? 'active' : ''} onClick={() => setTool('pan')}>拖动 H</button>
          <button onClick={() => setViewport({ x: 40, y: 40, scale: 0.5 })}>Fit</button>
          <button onClick={() => setViewport({ ...viewport, scale: 1 })}>100%</button>
          <button onClick={() => activePage && restoreHidden(activePage.pageId)}>恢复本页隐藏</button>
          <button onClick={saveAll} disabled={!project}>保存</button>
          <button onClick={exportProject} disabled={!project}>导出</button>
          <span>{message}</span>
        </header>
        <div className="canvasWrap">
          <Stage
            ref={stageRef}
            width={stageSize.width}
            height={stageSize.height}
            onMouseDown={onMouseDown}
            onMousemove={onMouseMove}
            onMouseup={onMouseUp}
            onContextMenu={(event) => event.evt.preventDefault()}
          >
            <Layer x={viewport.x} y={viewport.y} scaleX={viewport.scale} scaleY={viewport.scale}>
              {layouts.map((page) => {
                const manualPage = pageManual(page.pageId);
                const hidden = pageHiddenIds(page.pageId);
                return (
                  <Group key={page.pageId} x={page.offsetX} y={page.offsetY}>
                    <Rect width={page.width} height={page.height} fill="#fff" shadowColor="#000" shadowBlur={12} shadowOpacity={0.2} />
                    {images[page.pageId] && <KonvaImage image={images[page.pageId]} width={page.width} height={page.height} />}
                    <Text text={page.pageId} x={0} y={-24} fontSize={18} fill="#e5e7eb" />
                    {(page.candidates ?? []).map((candidate) => {
                      const isHidden = hidden.has(candidate.id);
                      if (isHidden && !reviewState?.filters.showHidden) return null;
                      if (!isHidden && reviewState?.filters.showCandidates === false) return null;
                      const color = isHidden ? colors.hidden ?? '#94a3b8' : colors.candidate ?? '#22c55e';
                      return (
                        <Rect
                          key={candidate.id}
                          x={candidate.bbox.x}
                          y={candidate.bbox.y}
                          width={candidate.bbox.width}
                          height={candidate.bbox.height}
                          stroke={color}
                          dash={isHidden ? [8, 6] : undefined}
                          strokeWidth={2}
                        />
                      );
                    })}
                    {(manualPage?.slices ?? []).map((slice) => {
                      const active = slice.id === activeSliceId;
                      const stroke = active ? colors.active ?? '#d946ef' : colors.selected ?? '#2563eb';
                      return (
                        <Group key={slice.id}>
                          <Rect x={slice.bbox.x} y={slice.bbox.y} width={slice.bbox.width} height={slice.bbox.height} stroke={stroke} strokeWidth={active ? 4 : 3} />
                          {active &&
                            handlesFor(slice.bbox).map((handle) => (
                              <Rect key={handle.name} x={handle.bbox.x} y={handle.bbox.y} width={handle.bbox.width} height={handle.bbox.height} fill="#fff" stroke="#111827" strokeWidth={1} />
                            ))}
                        </Group>
                      );
                    })}
                    {drag?.type === 'draw' && drag.pageId === page.pageId && (
                      <Group>
                        <Rect {...drag.draft} stroke="#000" strokeWidth={5} dash={[8, 6]} />
                        <Rect {...drag.draft} stroke="#fff" strokeWidth={2} dash={[8, 6]} />
                      </Group>
                    )}
                  </Group>
                );
              })}
            </Layer>
          </Stage>
        </div>
      </main>

      <aside className="rightPanel">
        <h2>Pages</h2>
        {layouts.map((page) => (
          <button key={page.pageId} className={activePageId === page.pageId ? 'active' : ''} onClick={() => setActivePageId(page.pageId)}>
            {page.pageId} · {page.candidates?.length ?? 0} candidates · {pageManual(page.pageId)?.slices.length ?? 0} selected
          </button>
        ))}
        <h2>Selected Assets</h2>
        <div className="assetList">
          {selectedSlices.map((slice) => (
            <div key={slice.id} className={activeSliceId === slice.id ? 'asset active' : 'asset'} onClick={() => setActiveSliceId(slice.id)}>
              <input
                name={`displayName-${slice.id}`}
                aria-label={`${slice.displayName} display name`}
                value={slice.displayName}
                onChange={(event) => updateSliceField(slice.pageId, slice.id, 'displayName', event.target.value)}
              />
              <select value={slice.kind} onChange={(event) => updateSliceField(slice.pageId, slice.id, 'kind', event.target.value as ManualSlice['kind'])}>
                <option value="image">image</option>
                <option value="icon">icon</option>
                <option value="basic">basic</option>
              </select>
              <small>{slice.pageId} · {slice.bbox.width}x{slice.bbox.height}</small>
              <button onClick={() => deleteSlice(slice.id)}>删除</button>
            </div>
          ))}
        </div>
      </aside>
    </div>
  );

  function updateSliceField<K extends keyof ManualSlice>(pageId: string, sliceId: string, key: K, value: ManualSlice[K]) {
    updateManualPage(pageId, (page) => ({ ...page, slices: page.slices.map((slice) => (slice.id === sliceId ? { ...slice, [key]: value } : slice)) }));
  }
}

function computeLayouts(pages: PageDoc[]): PageLayout[] {
  const layouts: PageLayout[] = [];
  let x = 0;
  let y = 0;
  let rowHeight = 0;
  pages.forEach((page, index) => {
    if (index > 0 && index % DEFAULT_COLS === 0) {
      x = 0;
      y += rowHeight + PAGE_GAP;
      rowHeight = 0;
    }
    layouts.push({ ...page, offsetX: x, offsetY: y });
    x += page.width + PAGE_GAP;
    rowHeight = Math.max(rowHeight, page.height);
  });
  return layouts;
}
