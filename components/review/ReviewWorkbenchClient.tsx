"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Bot, ChevronDown, ChevronLeft, ChevronRight, ChevronUp, Download, GripHorizontal, Grid2X2, Hand, Images, Lock, Minus, MousePointer2, PanelRightClose, PanelRightOpen, Plus, RotateCcw, Search, Sparkles, Square, Trash2, Upload, X } from "lucide-react";
import { Image as KonvaImage, Layer, Rect, Stage, Text, Transformer } from "react-konva";
import type Konva from "konva";
import { apiGet, apiUrl, createExportJob, deletePage, generateAiBoxes, getAiSliceSettings, getExportJob, renamePage, reorderPages, replacePage, saveSlices, uploadPages } from "@/components/api";
import { mergeAiBoxesIntoSlices } from "@/shared/ai-slices";
import { clamp, draftToBox, normalizeBox } from "@/shared/bbox";
import type { BBox, CreateExportJobRequest, CutMode, ExportJobRecord, PageRecord, ProjectDetail, SaveState, SliceRecord, ToolMode } from "@/shared/types";

type WorkbenchPage = PageRecord & {
  slices: SliceRecord[];
  image: HTMLImageElement | null;
};

type DragState =
  | { type: "draw"; start: Point; current: Point }
  | { type: "pan"; startClient: Point; originalPosition: Point };

type Point = { x: number; y: number };
type BBoxField = keyof BBox;
type BBoxDraft = Record<BBoxField, string>;

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

type AiProgress = {
  mode: "page" | "batch";
  total: number;
  completed: number;
  failed: number;
  added: number;
  skipped: number;
  currentLabel: string;
  message: string;
  minimized: boolean;
  hidden: boolean;
};

type ExportTarget = "assets" | "page" | "project";

const transformerAnchors = ["top-left", "top-center", "top-right", "middle-right", "bottom-right", "bottom-center", "bottom-left", "middle-left"];
const reviewColorStorageKey = "sliceStudio.reviewBoxColors.v1";
const reviewLanguageStorageKey = "sliceStudio.reviewLanguage.v1";
const boxSnapThreshold = 6;
const aiRevealDelayMinMs = 10_000;
const aiRevealDelayMaxMs = 15_000;
const exportJobPollIntervalMs = 1_000;
const exportJobPollTimeoutMs = 12 * 60_000;
const emptyBboxDraft: BBoxDraft = { x: "", y: "", width: "", height: "" };
const defaultBoxColors = {
  slice: "#0066cc",
  active: "#ff2d55"
};

type LanguageCode = "zh" | "en";

const reviewI18n = {
  zh: {
    reviewWorkbench: "审核工作台",
    untitledProject: "未命名项目",
    backToProjects: "返回项目列表",
    upload: "上传",
    undo: "撤销",
    redo: "重做",
    fit: "适配",
    zoomControls: "缩放控制",
    zoomOut: "缩小",
    zoomIn: "放大",
    nothingToUndo: "没有可撤销操作",
    redoUnavailable: "当前没有可重做记录",
    aiRunning: "处理中",
    batchRunning: "批量处理中",
    aiCurrent: "AI 当前页",
    aiAll: "AI 全部",
    assetsZip: "资产包",
    pageZip: "当前页包",
    projectZip: "项目包",
    language: "界面语言",
    chinese: "中文",
    english: "英文",
    saving: "保存中",
    saved: "已保存",
    saveFailed: "保存失败",
    ready: "就绪",
    pages: "页面",
    project: "项目",
    untitled: "未命名",
    assets: "资产",
    visible: "可见",
    noPages: "暂无页面",
    dragToReorder: "拖拽调整顺序",
    canvasTools: "画布工具",
    select: "选择",
    draw: "框选",
    pan: "拖动",
    selectTool: "选择工具",
    drawTool: "框选工具",
    panTool: "拖动画布工具",
    uploadHint: "上传 UI 截图后开始切图。",
    assetInspector: "资产检查器",
    expandInspector: "展开右侧面板",
    collapseInspector: "折叠右侧面板",
    expandAssetsList: "展开资产列表",
    collapseAssetsList: "折叠资产列表",
    searchAssetsPlaceholder: "搜索当前页资产...",
    searchAssets: "搜索当前页资产",
    filterByCropMode: "按裁切模式筛选",
    allModes: "全部模式",
    sortAssets: "资产排序",
    order: "顺序",
    name: "名称",
    size: "尺寸",
    selectAsset: "选择 {name}",
    assetName: "资产名称",
    cycleCropMode: "切换裁切模式",
    deleteAsset: "删除资产",
    noAssetsMatch: "当前视图没有匹配资产。",
    details: "详情",
    noAssetSelected: "未选择资产",
    overview: "总览",
    pageCropMode: "页面裁切模式",
    cropMode: "裁切模式",
    rect: "矩形",
    subject: "抠主体",
    innerImage: "保内图",
    mixed: "混合",
    inReview: "审核中",
    completed: "已完成",
    skipped: "已跳过",
    noPage: "暂无页面",
    pageName: "页面名称",
    replace: "替换",
    delete: "删除",
    boxColor: "框颜色",
    reset: "重置",
    normal: "普通",
    active: "选中",
    normalBoxColor: "普通框颜色",
    activeBoxColor: "选中框颜色",
    activeAsset: "当前资产",
    page: "页面",
    format: "格式",
    locked: "锁定",
    off: "关闭",
    lockedMissingInterface: "缺少接口：SliceRecord 目前没有 locked 字段",
    deleteCurrentAsset: "删除当前资产",
    deleteSelectedAssets: "删除选中资产",
    copiedAssets: "已复制 {count} 个资产。",
    pastedAssets: "已粘贴 {count} 个资产。",
    movedAssets: "已移动 {count} 个资产。",
    retrySave: "重试保存",
    unsavedEditsHeld: "保存失败，当前编辑仍保留在页面中。",
    pageStartHint: "顶部按钮可上传 1..N 张图片。",
    createAssetHint: "使用框选工具创建资产，再用选择工具调整。",
    canvasReadyHint: "画布已准备好接收源图。",
    aiDetectionProgress: "AI 检测进度",
    aiBatchProcessingRunning: "AI 批量处理中",
    aiCurrentPage: "AI 当前页",
    total: "总计",
    newAssets: "新增资产",
    failed: "失败",
    expandAiProgress: "展开 AI 进度",
    minimizeAiProgress: "最小化 AI 进度",
    expand: "展开",
    minimize: "最小化",
    hideAiProgress: "隐藏 AI 进度",
    hide: "隐藏",
    close: "关闭",
    deleteCurrentPageQuestion: "删除当前页面？",
    replaceCurrentPageQuestion: "替换当前页面？",
    deleteCurrentPageDescription: "该页面的原图和所有切图都会被删除，剩余页面会重新编号。",
    replaceCurrentPageDescription: "将使用“{file}”替换当前页面原图，并清空该页已有切图。",
    cancel: "取消",
    confirmDelete: "确认删除",
    confirmReplace: "确认替换",
    assetOverview: "资产总览",
    clickCardToLocate: "点击卡片定位资产",
    assetOverviewPagination: "资产总览翻页",
    previousPage: "上一页",
    nextPage: "下一页",
    closeAssetOverview: "关闭资产总览",
    noAssetsOnPage: "当前页暂无资产",
    assetCropMode: "{name} 裁切模式：{mode}",
    pageCropModeAria: "页面裁切模式",
    loadingProject: "正在读取项目。",
    projectRestored: "项目已恢复。继续切图会自动保存。",
    projectCreated: "项目已创建。上传 UI 截图开始。",
    loadFailed: "读取失败：{error}",
    sourceUndoUnavailable: "该操作涉及页面原图文件，无法完整撤销；已按当前磁盘状态重新载入项目。",
    undone: "已撤销：{label}",
    undoSaveFailed: "撤销保存失败：{error}",
    uploadingImages: "正在上传 {count} 张图片。",
    uploadedImages: "已上传 {count} 张图片。",
    uploadFailed: "上传失败：{error}",
    savedStatus: "已保存。",
    saveFailedStatus: "保存失败：{error}",
    pageNameSaved: "页面名称已保存。",
    pageNameSaveFailed: "页面名称保存失败：{error}",
    exportedAssets: "已导出 {count} 个切图。",
    exportedAssetsCached: "项目未变化，已复用上次资产包：{count} 个切图。",
    exportedPage: "已导出当前页 Pencil 项目：{assets} 个图层资产。",
    exportedPageCached: "当前页未变化，已复用上次 Pencil 项目：{assets} 个图层资产。",
    exportedProject: "已导出项目包：{pages} 页，{assets} 个图层资产。",
    exportedProjectCached: "项目未变化，已复用上次项目包：{pages} 页，{assets} 个图层资产。",
    exportingAssets: "正在准备资产包。未修改内容会直接复用上次导出。",
    exportingPage: "正在准备当前页项目包。未修改内容会直接复用上次导出。",
    exportingProject: "正在准备项目包。未修改内容会直接复用上次导出。",
    exportQueued: "导出任务已排队。",
    exportRunning: "正在生成导出文件，完成后会自动下载。",
    exportTimedOut: "导出仍在后台处理中，请稍后重试或刷新后再次查看。",
    exporting: "导出中",
    exportFailed: "导出失败：{error}",
    newAssetsWillUseMode: "后续新建资产将使用{mode}模式。",
    currentPageAlreadyMode: "当前页已是{mode}模式。",
    pageOrderSaved: "页面顺序已保存。",
    pageReorderFailed: "页面排序失败：{error}",
    pageDeleted: "页面已删除。",
    pageReplaced: "页面已替换，该页已有切图已清空。",
    pageActionFailed: "{action}页面失败：{error}",
    aiDetecting: "AI 正在检测 {label}",
    aiPreparingResults: "正在整理 {label} 的候选框",
    aiBatchPreparingPage: "正在整理 {label} 的候选框 · {done}/{total}",
    noNewBoxes: "AI 未新增框，跳过 {skipped} 个。",
    noNewAiBoxes: "AI 未新增框。已跳过 {skipped} 个重复或无效框。",
    aiAddedSkipped: "AI 已新增 {added} 个，跳过 {skipped} 个。",
    aiAddedStatus: "AI 已新增 {added} 个矩形框，跳过 {skipped} 个。",
    aiDetectionFailed: "AI 检测失败：{error}",
    aiBatchDetection: "AI 批量检测 {done}/{total}",
    aiBatchDetectingPage: "AI 批量检测 {label} · {done}/{total}",
    aiBatchAdded: "AI 批量检测 {done}/{total} · 新增 {added}",
    aiBatchComplete: "AI 批量完成：成功 {completed} 页，失败 {failed} 页",
    aiBatchCompleteStatus: "AI 批量完成：成功 {completed} 页，失败 {failed} 页，新增 {added} 个，跳过 {skipped} 个。",
    aiBatchFailed: "AI 批量检测失败：{error}",
    undoEdit: "编辑",
    undoRenamePage: "页面重命名",
    undoCreateAsset: "新建资产",
    undoAiBoxes: "AI 画框",
    undoAiBatchBoxes: "AI 批量画框",
    undoEditAsset: "编辑资产",
    undoChangePageCropMode: "批量切换裁切模式",
    undoDeleteAsset: "删除资产",
    undoDeleteAssets: "删除多个资产",
    undoPasteAssets: "粘贴资产",
    undoMoveAssets: "移动资产",
    undoResizeAsset: "调整资产尺寸",
    undoMoveAsset: "移动资产",
    undoReorderPages: "页面排序",
    undoDeletePage: "删除页面",
    undoReplacePage: "替换页面",
    undoEditBbox: "编辑坐标",
    undoChangeCropMode: "切换裁切模式"
  },
  en: {
    reviewWorkbench: "Review Workbench",
    untitledProject: "Untitled Project",
    backToProjects: "Back to projects",
    upload: "Upload",
    undo: "Undo",
    redo: "Redo",
    fit: "Fit",
    zoomControls: "Zoom controls",
    zoomOut: "Zoom out",
    zoomIn: "Zoom in",
    nothingToUndo: "Nothing to undo",
    redoUnavailable: "Redo is not available until a redo stack exists",
    aiRunning: "Processing",
    batchRunning: "Batch Processing",
    aiCurrent: "AI Current",
    aiAll: "AI All",
    assetsZip: "Assets.zip",
    pageZip: "Current page",
    projectZip: "Project package",
    language: "Interface language",
    chinese: "Chinese",
    english: "English",
    saving: "Saving",
    saved: "Saved",
    saveFailed: "Save failed",
    ready: "Ready",
    pages: "Pages",
    project: "Project",
    untitled: "Untitled",
    assets: "assets",
    visible: "visible",
    noPages: "No pages",
    dragToReorder: "Drag to reorder",
    canvasTools: "Canvas tools",
    select: "Select",
    draw: "Draw",
    pan: "Pan",
    selectTool: "Select tool",
    drawTool: "Draw tool",
    panTool: "Pan tool",
    uploadHint: "Upload UI screenshots to start slicing.",
    assetInspector: "Asset inspector",
    expandInspector: "Expand inspector",
    collapseInspector: "Collapse inspector",
    expandAssetsList: "Expand assets list",
    collapseAssetsList: "Collapse assets list",
    searchAssetsPlaceholder: "Search assets on this page...",
    searchAssets: "Search assets on this page",
    filterByCropMode: "Filter by crop mode",
    allModes: "All modes",
    sortAssets: "Sort assets",
    order: "Order",
    name: "Name",
    size: "Size",
    selectAsset: "Select {name}",
    assetName: "Asset name",
    cycleCropMode: "Cycle crop mode",
    deleteAsset: "Delete asset",
    noAssetsMatch: "No assets match this view.",
    details: "Details",
    noAssetSelected: "No asset selected",
    overview: "Overview",
    pageCropMode: "Page Crop Mode",
    cropMode: "Crop Mode",
    rect: "Rect",
    subject: "Subject",
    innerImage: "Inner Image",
    mixed: "Mixed",
    inReview: "In Review",
    completed: "Completed",
    skipped: "Skipped",
    noPage: "No page",
    pageName: "Page name",
    replace: "Replace",
    delete: "Delete",
    boxColor: "Box Color",
    reset: "Reset",
    normal: "Normal",
    active: "Active",
    normalBoxColor: "Normal box color",
    activeBoxColor: "Active box color",
    activeAsset: "Active asset",
    page: "Page",
    format: "Format",
    locked: "Locked",
    off: "Off",
    lockedMissingInterface: "Missing interface: SliceRecord has no locked field yet",
    deleteCurrentAsset: "Delete current asset",
    deleteSelectedAssets: "Delete selected assets",
    copiedAssets: "Copied {count} asset(s).",
    pastedAssets: "Pasted {count} asset(s).",
    movedAssets: "Moved {count} asset(s).",
    retrySave: "Retry save",
    unsavedEditsHeld: "Save failed. Current edits are still kept on this page.",
    pageStartHint: "Upload 1..N images from the top bar.",
    createAssetHint: "Use Draw to create assets, then Select to adjust them.",
    canvasReadyHint: "The canvas is ready for a source image.",
    aiDetectionProgress: "AI detection progress",
    aiBatchProcessingRunning: "AI Batch Processing Running",
    aiCurrentPage: "AI Current Page",
    total: "Total",
    newAssets: "New Assets",
    failed: "Failed",
    expandAiProgress: "Expand AI progress",
    minimizeAiProgress: "Minimize AI progress",
    expand: "Expand",
    minimize: "Minimize",
    hideAiProgress: "Hide AI progress",
    hide: "Hide",
    close: "Close",
    deleteCurrentPageQuestion: "Delete current page?",
    replaceCurrentPageQuestion: "Replace current page?",
    deleteCurrentPageDescription: "The source image and all slices on this page will be deleted. Remaining pages will be renumbered.",
    replaceCurrentPageDescription: "This will replace the current source image with \"{file}\" and clear existing slices on this page.",
    cancel: "Cancel",
    confirmDelete: "Delete",
    confirmReplace: "Replace",
    assetOverview: "Asset Overview",
    clickCardToLocate: "Click a card to locate it",
    assetOverviewPagination: "Asset overview pagination",
    previousPage: "Previous page",
    nextPage: "Next page",
    closeAssetOverview: "Close asset overview",
    noAssetsOnPage: "No assets on this page",
    assetCropMode: "{name} crop mode: {mode}",
    pageCropModeAria: "Page crop mode",
    loadingProject: "Loading project.",
    projectRestored: "Project restored. Changes will auto-save.",
    projectCreated: "Project created. Upload UI screenshots to start.",
    loadFailed: "Load failed: {error}",
    sourceUndoUnavailable: "This action changed a source image file and cannot be fully undone. Reloaded the current project state from disk.",
    undone: "Undone: {label}",
    undoSaveFailed: "Undo save failed: {error}",
    uploadingImages: "Uploading {count} image(s).",
    uploadedImages: "Uploaded {count} image(s).",
    uploadFailed: "Upload failed: {error}",
    savedStatus: "Saved.",
    saveFailedStatus: "Save failed: {error}",
    pageNameSaved: "Page name saved.",
    pageNameSaveFailed: "Page name save failed: {error}",
    exportedAssets: "Exported {count} assets.",
    exportedAssetsCached: "Project unchanged. Reused the previous assets package: {count} assets.",
    exportedPage: "Exported current page Pencil project: {assets} layer assets.",
    exportedPageCached: "Current page unchanged. Reused the previous Pencil package: {assets} layer assets.",
    exportedProject: "Exported project package: {pages} pages, {assets} layer assets.",
    exportedProjectCached: "Project unchanged. Reused the previous project package: {pages} pages, {assets} layer assets.",
    exportingAssets: "Preparing assets package. Unchanged content will reuse the previous export.",
    exportingPage: "Preparing current page package. Unchanged content will reuse the previous export.",
    exportingProject: "Preparing project package. Unchanged content will reuse the previous export.",
    exportQueued: "Export job queued.",
    exportRunning: "Generating the export. It will download automatically when ready.",
    exportTimedOut: "The export is still running in the background. Try again later or refresh and check again.",
    exporting: "Exporting",
    exportFailed: "Export failed: {error}",
    newAssetsWillUseMode: "New assets will use {mode} mode.",
    currentPageAlreadyMode: "Current page already uses {mode} mode.",
    pageOrderSaved: "Page order saved.",
    pageReorderFailed: "Page reorder failed: {error}",
    pageDeleted: "Page deleted.",
    pageReplaced: "Page replaced. Existing slices on that page were cleared.",
    pageActionFailed: "{action} page failed: {error}",
    aiDetecting: "AI is detecting {label}",
    aiPreparingResults: "Preparing candidate boxes for {label}",
    aiBatchPreparingPage: "Preparing candidate boxes for {label} · {done}/{total}",
    noNewBoxes: "No new boxes. Skipped {skipped}.",
    noNewAiBoxes: "No new AI boxes. Skipped {skipped} duplicate or invalid boxes.",
    aiAddedSkipped: "Added {added}. Skipped {skipped}.",
    aiAddedStatus: "AI added {added} boxes and skipped {skipped}.",
    aiDetectionFailed: "AI detection failed: {error}",
    aiBatchDetection: "AI batch detection {done}/{total}",
    aiBatchDetectingPage: "AI batch detection {label} · {done}/{total}",
    aiBatchAdded: "AI batch detection {done}/{total} · added {added}",
    aiBatchComplete: "AI batch complete: {completed} completed, {failed} failed",
    aiBatchCompleteStatus: "AI batch complete: {completed} completed, {failed} failed, {added} added, {skipped} skipped.",
    aiBatchFailed: "AI batch detection failed: {error}",
    undoEdit: "Edit",
    undoRenamePage: "Rename page",
    undoCreateAsset: "Create asset",
    undoAiBoxes: "AI boxes",
    undoAiBatchBoxes: "AI batch boxes",
    undoEditAsset: "Edit asset",
    undoChangePageCropMode: "Change page crop mode",
    undoDeleteAsset: "Delete asset",
    undoDeleteAssets: "Delete assets",
    undoPasteAssets: "Paste assets",
    undoMoveAssets: "Move assets",
    undoResizeAsset: "Resize asset",
    undoMoveAsset: "Move asset",
    undoReorderPages: "Reorder pages",
    undoDeletePage: "Delete page",
    undoReplacePage: "Replace page",
    undoEditBbox: "Edit bbox",
    undoChangeCropMode: "Change crop mode"
  }
} satisfies Record<LanguageCode, Record<string, string>>;

type ReviewText = typeof reviewI18n.zh;

export function ReviewWorkbenchClient({ projectId }: { projectId: string }) {
  const [language, setLanguage] = useState<LanguageCode>("zh");
  const [detail, setDetail] = useState<ProjectDetail | null>(null);
  const [pages, setPages] = useState<WorkbenchPage[]>([]);
  const [activePageId, setActivePageId] = useState<string | null>(null);
  const [activeSliceId, setActiveSliceId] = useState<string | null>(null);
  const [selectedSliceIds, setSelectedSliceIds] = useState<string[]>([]);
  const [tool, setTool] = useState<ToolMode>("select");
  const [scale, setScale] = useState(1);
  const [stagePosition, setStagePosition] = useState<Point>({ x: 80, y: 80 });
  const [drag, setDrag] = useState<DragState | null>(null);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [status, setStatus] = useState(reviewI18n.zh.loadingProject);
  const [stageSize, setStageSize] = useState({ width: 1000, height: 700 });
  const [inspectorCollapsed, setInspectorCollapsed] = useState(false);
  const [assetListCollapsed, setAssetListCollapsed] = useState(false);
  const [assetSearch, setAssetSearch] = useState("");
  const [assetCutModeFilter, setAssetCutModeFilter] = useState<"all" | CutMode>("all");
  const [assetSort, setAssetSort] = useState<"order" | "name" | "size">("order");
  const [undoStack, setUndoStack] = useState<UndoSnapshot[]>([]);
  const [pageConfirmAction, setPageConfirmAction] = useState<PageConfirmAction | null>(null);
  const [draggingPageId, setDraggingPageId] = useState<string | null>(null);
  const [boxColors, setBoxColors] = useState(defaultBoxColors);
  const [defaultCutMode, setDefaultCutMode] = useState<CutMode>("rect");
  const [galleryOpen, setGalleryOpen] = useState(false);
  const [aiRunning, setAiRunning] = useState<"page" | "batch" | null>(null);
  const [aiProgress, setAiProgress] = useState<AiProgress | null>(null);
  const [exportTarget, setExportTarget] = useState<ExportTarget | null>(null);
  const [previewRevisionBySliceId, setPreviewRevisionBySliceId] = useState<Record<string, number>>({});
  const [pageThumbnailRevisionById, setPageThumbnailRevisionById] = useState<Record<string, number>>({});
  const [pendingPreviewSliceIds, setPendingPreviewSliceIds] = useState<Set<string>>(() => new Set());
  const [bboxDraft, setBboxDraft] = useState<BBoxDraft>(emptyBboxDraft);
  const stageWrapRef = useRef<HTMLDivElement | null>(null);
  const stageRef = useRef<Konva.Stage | null>(null);
  const transformerRef = useRef<Konva.Transformer | null>(null);
  const activeNameInputRef = useRef<HTMLInputElement | null>(null);
  const languageRef = useRef<LanguageCode>("zh");
  const sliceNodeRefs = useRef<Record<string, Konva.Rect | null>>({});
  const assetItemRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const saveQueueRef = useRef<Promise<void>>(Promise.resolve());
  const saveSequenceRef = useRef(0);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pageRenameTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingPageRenameRef = useRef<{ pageId: string; displayName: string } | null>(null);
  const pageRenameUndoRef = useRef<string | null>(null);
  const sliceEditUndoRef = useRef<string | null>(null);
  const copiedSlicesRef = useRef<SliceRecord[]>([]);
  const replaceInputRef = useRef<HTMLInputElement | null>(null);
  const activePageIdRef = useRef<string | null>(null);
  const pagesRef = useRef<WorkbenchPage[]>([]);
  const imageLoadRef = useRef<Record<string, Promise<HTMLImageElement>>>({});
  const text = reviewI18n[language];

  const activePage = pages.find((page) => page.id === activePageId) || null;
  const activeSlice = activePage?.slices.find((slice) => slice.id === activeSliceId) || null;
  const hasSlices = pages.some((page) => page.slices.length > 0);
  const totalAssets = pages.reduce((total, page) => total + page.slices.length, 0);
  const activePageAssetCount = activePage?.slices.length || 0;
  const saveLabel = saveState === "saving" ? text.saving : saveState === "saved" ? text.saved : saveState === "error" ? text.saveFailed : text.ready;
  const pageIndex = activePage ? pages.findIndex((page) => page.id === activePage.id) : -1;
  const pageCutMode = getPageCutMode(activePage, defaultCutMode);
  const aiBusy = aiRunning !== null;
  const exportBusy = exportTarget !== null;
  const visibleAssets = useMemo(() => {
    const query = assetSearch.trim().toLowerCase();
    const source = activePage?.slices || [];
    return source
      .filter((slice) => !query || slice.name.toLowerCase().includes(query))
      .filter((slice) => assetCutModeFilter === "all" || slice.cutMode === assetCutModeFilter)
      .slice()
      .sort((left, right) => {
        if (assetSort === "name") return left.name.localeCompare(right.name);
        if (assetSort === "size") return sliceArea(right) - sliceArea(left);
        return left.sliceIndex - right.sliceIndex;
      });
  }, [activePage, assetCutModeFilter, assetSearch, assetSort]);

  function changeLanguage(nextLanguage: LanguageCode) {
    languageRef.current = nextLanguage;
    setLanguage(nextLanguage);
    window.localStorage.setItem(reviewLanguageStorageKey, nextLanguage);
  }

  const loadProject = useCallback(async () => {
    const messages = reviewI18n[languageRef.current];
    const projectDetail = await apiGet<ProjectDetail>(`/api/projects/${projectId}`);
    const hydratedPages = hydratePages(projectDetail.pages);
    setDetail(projectDetail);
    setPages(hydratedPages);
    const currentPageId = activePageIdRef.current;
    const nextActivePageId = currentPageId && hydratedPages.some((page) => page.id === currentPageId)
      ? currentPageId
      : hydratedPages[0]?.id || null;
    setActivePageId(nextActivePageId);
    selectSlice(null);
    setStatus(hydratedPages.length ? messages.projectRestored : messages.projectCreated);
  }, [projectId]);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(reviewLanguageStorageKey);
      if (stored === "zh" || stored === "en") {
        languageRef.current = stored;
        setLanguage(stored);
      }
    } catch {
      languageRef.current = "zh";
      setLanguage("zh");
    }
  }, []);

  useEffect(() => {
    languageRef.current = language;
    document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
  }, [language]);

  useEffect(() => {
    pagesRef.current = pages;
  }, [pages]);

  useEffect(() => {
    activePageIdRef.current = activePageId;
  }, [activePageId]);

  useEffect(() => {
    if (!activePageId || activePage?.image) return;
    void ensurePageImage(activePageId).catch((error) => {
      setStatus(formatMessage(reviewI18n[languageRef.current].loadFailed, { error: getErrorMessage(error) }));
    });
  }, [activePage?.image, activePageId]);

  useEffect(() => {
    void loadProject().catch((error) => {
      const messages = reviewI18n[languageRef.current];
      setStatus(formatMessage(messages.loadFailed, { error: getErrorMessage(error) }));
    });
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
    const transformer = transformerRef.current;
    if (!transformer) return;
    const activeNode = activeSliceId ? sliceNodeRefs.current[activeSliceId] : null;
    transformer.nodes(tool === "select" && activeNode ? [activeNode] : []);
    transformer.getLayer()?.batchDraw();
  }, [activeSliceId, tool, pages]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && galleryOpen) {
        event.preventDefault();
        setGalleryOpen(false);
        return;
      }
      const target = event.target as HTMLElement | null;
      if (target && ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName)) {
        if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "z") {
          event.preventDefault();
          void restoreUndo();
        }
        return;
      }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "z") {
        event.preventDefault();
        void restoreUndo();
        return;
      }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "c") {
        event.preventDefault();
        copySelectedSlices();
        return;
      }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "v") {
        event.preventDefault();
        pasteCopiedSlices();
        return;
      }
      if (event.key.toLowerCase() === "v") setTool("select");
      if (event.key.toLowerCase() === "b") setTool("draw");
      if (event.key.toLowerCase() === "h") setTool("pan");
      if (isArrowKey(event.key)) {
        event.preventDefault();
        nudgeSelectedSlices(arrowDelta(event.key, event.shiftKey ? 10 : 1));
        return;
      }
      if ((event.key === "Enter" || event.key === "F2") && activeSliceId) {
        event.preventDefault();
        focusActiveAssetName();
        return;
      }
      if (event.key === "Delete" || event.key === "Backspace") {
        event.preventDefault();
        deleteSelectedSlices();
      }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        void saveNow().catch(() => undefined);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  });

  useEffect(() => {
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      if (saveState !== "saving" && saveState !== "error") return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [saveState]);

  useEffect(() => {
    if (!activeSliceId) return;
    assetItemRefs.current[activeSliceId]?.scrollIntoView({ block: "nearest" });
  }, [activeSliceId]);

  useEffect(() => {
    if (!activeSlice) {
      setBboxDraft(emptyBboxDraft);
      return;
    }
    setBboxDraft({
      x: String(activeSlice.bbox.x),
      y: String(activeSlice.bbox.y),
      width: String(activeSlice.bbox.width),
      height: String(activeSlice.bbox.height)
    });
  }, [activeSlice?.id, activeSlice?.bbox.x, activeSlice?.bbox.y, activeSlice?.bbox.width, activeSlice?.bbox.height]);

  function hydratePages(sourcePages: ProjectDetail["pages"], resetImagePageIds = new Set<string>()): WorkbenchPage[] {
    return sourcePages.map((page) => {
      const existing = pagesRef.current.find((current) => current.id === page.id);
      return {
        ...page,
        image: !resetImagePageIds.has(page.id) ? existing?.image || null : null
      };
    });
  }

  async function ensurePageImage(pageId: string): Promise<HTMLImageElement | null> {
    const existingPage = pagesRef.current.find((page) => page.id === pageId);
    if (!existingPage) return null;
    if (existingPage.image) return existingPage.image;
    if (!imageLoadRef.current[pageId]) {
      imageLoadRef.current[pageId] = loadImage(apiUrl(existingPage.sourceUrl));
    }
    try {
      const image = await imageLoadRef.current[pageId];
      setPages((current) => current.map((page) => page.id === pageId ? { ...page, image } : page));
      return image;
    } catch (error) {
      delete imageLoadRef.current[pageId];
      throw error;
    }
  }

  async function applyProjectDetail(projectDetail: ProjectDetail, nextActivePageId?: string | null, nextActiveSliceId?: string | null, resetImagePageIds = new Set<string>()) {
    const hydratedPages = hydratePages(projectDetail.pages, resetImagePageIds);
    setDetail(projectDetail);
    setPages(hydratedPages);
    const resolvedPageId = nextActivePageId && hydratedPages.some((page) => page.id === nextActivePageId)
      ? nextActivePageId
      : hydratedPages[0]?.id || null;
    setActivePageId(resolvedPageId);
    const activePageForSlice = hydratedPages.find((page) => page.id === resolvedPageId);
    selectSlice(nextActiveSliceId && activePageForSlice?.slices.some((slice) => slice.id === nextActiveSliceId) ? nextActiveSliceId : null);
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
      setStatus(text.sourceUndoUnavailable);
      await loadProject();
      return;
    }

    const restoredPages = clonePagesForUndo(snapshot.pages);
    setPages(restoredPages);
    setActivePageId(snapshot.activePageId);
    selectSlice(snapshot.activeSliceId);
    setStatus(formatMessage(text.undone, { label: snapshot.label }));
    setSaveState("saving");
    try {
      await reorderPages(projectId, restoredPages.map((page) => page.id));
      await Promise.all(restoredPages.map((page) => renamePage(projectId, page.id, page.displayName)));
      await saveSlices(projectId, serializeSlices(restoredPages, snapshot.activePageId));
      setSaveState("saved");
    } catch (error) {
      setSaveState("error");
      setStatus(formatMessage(text.undoSaveFailed, { error: getErrorMessage(error) }));
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
      setStatus(formatMessage(text.uploadingImages, { count: images.length }));
      await uploadPages(projectId, images);
      await loadProject();
      setStatus(formatMessage(text.uploadedImages, { count: images.length }));
    } catch (error) {
      setStatus(formatMessage(text.uploadFailed, { error: getErrorMessage(error) }));
    }
  }

  function scheduleSave(nextPages: WorkbenchPage[], options: { pushUndo?: boolean; undoLabel?: string } = {}) {
    if (options.pushUndo) pushUndo(options.undoLabel || text.undoEdit);
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
    const saveSequence = ++saveSequenceRef.current;
    const payload = serializeSlices(pagesToSave, activePageId);
    setSaveState("saving");
    const queuedSave = saveQueueRef.current.then(async () => {
      await saveSlices(projectId, payload);
    });
    saveQueueRef.current = queuedSave.catch(() => undefined);
    try {
      await queuedSave;
      if (saveSequence === saveSequenceRef.current) {
        setPendingPreviewSliceIds(new Set());
        setSaveState("saved");
        setStatus(text.savedStatus);
      }
    } catch (error) {
      if (saveSequence === saveSequenceRef.current) {
        setSaveState("error");
        setStatus(formatMessage(text.saveFailedStatus, { error: getErrorMessage(error) }));
      }
      throw error;
    }
  }

  async function savePagesWithActive(pagesToSave: WorkbenchPage[], nextActivePageId = activePageId) {
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
    const saveSequence = ++saveSequenceRef.current;
    const payload = serializeSlices(pagesToSave, nextActivePageId);
    setSaveState("saving");
    const queuedSave = saveQueueRef.current.then(async () => {
      await saveSlices(projectId, payload);
    });
    saveQueueRef.current = queuedSave.catch(() => undefined);
    await queuedSave;
    if (saveSequence === saveSequenceRef.current) {
      setPendingPreviewSliceIds(new Set());
      setSaveState("saved");
      setStatus(text.savedStatus);
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
      pushUndo(text.undoRenamePage);
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
      setStatus(text.pageNameSaved);
      pageRenameUndoRef.current = null;
    } catch (error) {
      setSaveState("error");
      setStatus(formatMessage(text.pageNameSaveFailed, { error: getErrorMessage(error) }));
      throw error;
    }
  }

  async function exportAssets() {
    if (exportBusy) return;
    setExportTarget("assets");
    setStatus(text.exportingAssets);
    try {
      await flushPageRename();
      await saveNow();
      const result = await runExportJob({
        kind: "assets"
      });
      triggerDownload(result.url);
      setStatus(formatMessage(result.cached ? text.exportedAssetsCached : text.exportedAssets, { count: result.assetCount }));
    } catch (error) {
      setStatus(formatMessage(text.exportFailed, { error: getErrorMessage(error) }));
    } finally {
      setExportTarget(null);
    }
  }

  async function exportProject() {
    if (exportBusy) return;
    setExportTarget("project");
    setStatus(text.exportingProject);
    try {
      await flushPageRename();
      await saveNow();
      const result = await runExportJob({
        kind: "project"
      });
      triggerDownload(result.url);
      setStatus(formatMessage(result.cached ? text.exportedProjectCached : text.exportedProject, { pages: result.pageCount || 0, assets: result.assetCount }));
    } catch (error) {
      setStatus(formatMessage(text.exportFailed, { error: getErrorMessage(error) }));
    } finally {
      setExportTarget(null);
    }
  }

  async function exportCurrentPage() {
    if (!activePage || exportBusy) return;
    setExportTarget("page");
    setStatus(text.exportingPage);
    try {
      await flushPageRename();
      await saveNow();
      const result = await runExportJob({
        kind: "page_project",
        pageId: activePage.id
      });
      triggerDownload(result.url);
      setStatus(formatMessage(result.cached ? text.exportedPageCached : text.exportedPage, { assets: result.assetCount }));
    } catch (error) {
      setStatus(formatMessage(text.exportFailed, { error: getErrorMessage(error) }));
    } finally {
      setExportTarget(null);
    }
  }

  async function runExportJob(payload: CreateExportJobRequest): Promise<Required<Pick<ExportJobRecord, "assetCount" | "url">> & Pick<ExportJobRecord, "pageCount" | "cached">> {
    const created = await createExportJob(projectId, payload);
    setStatus(created.job.status === "queued" ? text.exportQueued : created.job.message || text.exportRunning);
    const startedAt = Date.now();
    let job = created.job;
    while (job.status === "queued" || job.status === "running") {
      if (Date.now() - startedAt > exportJobPollTimeoutMs) throw new Error(text.exportTimedOut);
      await sleep(exportJobPollIntervalMs);
      job = (await getExportJob(projectId, job.id)).job;
      setStatus(job.status === "queued" ? text.exportQueued : job.message || text.exportRunning);
    }
    if (job.status === "failed") throw new Error(job.error || job.message || "Export failed");
    if (!job.url || typeof job.assetCount !== "number") throw new Error("Export job finished without a download URL");
    return {
      assetCount: job.assetCount,
      pageCount: job.pageCount,
      url: job.url,
      cached: job.cached
    };
  }

  function triggerDownload(url: string) {
    const link = document.createElement("a");
    link.href = apiUrl(url);
    link.download = "";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  function sleep(ms: number): Promise<void> {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
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
    if (isTransformerTarget(target)) return;
    const sliceId = target.attrs.sliceId as string | undefined;
    if (sliceId) {
      selectSlice(sliceId);
      return;
    }
    if (target === target.getStage()) selectSlice(null);
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
      cutMode: pageCutMode === "mixed" ? defaultCutMode : pageCutMode,
      bbox: normalizeBox(bbox, activePage),
      selected: true
    };
    const nextPages = pages.map((page) => page.id === activePage.id ? { ...page, slices: [...page.slices, slice] } : page);
    selectSlice(slice.id);
    setPendingPreviewSliceIds((current) => new Set([...current, slice.id]));
    scheduleSave(nextPages, { pushUndo: true, undoLabel: text.undoCreateAsset });
  }

  function aiRevealDelayMs(): number {
    return Math.round(aiRevealDelayMinMs + Math.random() * (aiRevealDelayMaxMs - aiRevealDelayMinMs));
  }

  function wait(ms: number): Promise<void> {
    return new Promise((resolve) => {
      window.setTimeout(resolve, ms);
    });
  }

  async function runAiForCurrentPage() {
    if (!activePage || aiBusy) return;
    const label = `P${pageIndex + 1}`;
    setAiRunning("page");
    setAiProgress({
      mode: "page",
      total: 1,
      completed: 0,
      failed: 0,
      added: 0,
      skipped: 0,
      currentLabel: label,
      message: formatMessage(text.aiDetecting, { label }),
      minimized: false,
      hidden: false
    });
    setStatus(`${formatMessage(text.aiDetecting, { label })}。`);
    try {
      await flushPageRename();
      const response = await generateAiBoxes(projectId, activePage.id);
      setAiProgress((current) => current ? {
        ...current,
        message: formatMessage(text.aiPreparingResults, { label })
      } : current);
      setStatus(`${formatMessage(text.aiPreparingResults, { label })}。`);
      await wait(aiRevealDelayMs());
      const currentPages = pagesRef.current;
      const currentPage = currentPages.find((page) => page.id === activePage.id);
      if (!currentPage) return;
      const merged = mergeAiBoxesIntoSlices({
        projectId,
        page: currentPage,
        boxes: response.boxes,
        cutMode: "rect",
        idSeed: `p${pageIndex + 1}_${Date.now().toString(36)}`
      });
      const skipped = merged.skippedCount + response.diagnostics.rejectedBoxCount;
      if (!merged.addedCount) {
        setAiProgress((current) => current ? {
          ...current,
          completed: 1,
          added: 0,
          skipped,
          message: formatMessage(text.noNewBoxes, { skipped })
        } : current);
        setStatus(formatMessage(text.noNewAiBoxes, { skipped }));
        return;
      }
      pushUndo(text.undoAiBoxes);
      const nextPages = currentPages.map((page) => page.id === currentPage.id ? { ...page, slices: merged.slices } : page);
      const previousIds = new Set(currentPage.slices.map((slice) => slice.id));
      const addedIds = merged.slices.filter((slice) => !previousIds.has(slice.id)).map((slice) => slice.id);
      setPendingPreviewSliceIds((current) => new Set([...current, ...addedIds]));
      pagesRef.current = nextPages;
      setPages(nextPages);
      selectSlice(merged.lastAddedSliceId);
      await savePagesWithActive(nextPages, currentPage.id);
      setAiProgress((current) => current ? {
        ...current,
        completed: 1,
        added: merged.addedCount,
        skipped,
        message: formatMessage(text.aiAddedSkipped, { added: merged.addedCount, skipped })
      } : current);
      setStatus(formatMessage(text.aiAddedStatus, { added: merged.addedCount, skipped }));
    } catch (error) {
      setSaveState("error");
      setAiProgress((current) => current ? {
        ...current,
        completed: 1,
        failed: 1,
        message: formatMessage(text.aiDetectionFailed, { error: getErrorMessage(error) })
      } : current);
      setStatus(formatMessage(text.aiDetectionFailed, { error: getErrorMessage(error) }));
    } finally {
      setAiRunning(null);
    }
  }

  async function runAiForAllPages() {
    if (!pages.length || aiBusy) return;
    setAiRunning("batch");
    setAiProgress({
      mode: "batch",
      total: pages.length,
      completed: 0,
      failed: 0,
      added: 0,
      skipped: 0,
      currentLabel: "",
      message: formatMessage(text.aiBatchDetection, { done: 0, total: pages.length }),
      minimized: false,
      hidden: false
    });
    setStatus(`${formatMessage(text.aiBatchDetection, { done: 0, total: pages.length })}。`);
    let workingPages = pages;
    let completed = 0;
    let failed = 0;
    let addedTotal = 0;
    let skippedTotal = 0;
    let mergeQueue = Promise.resolve();
    pushUndo(text.undoAiBatchBoxes);
    try {
      await flushPageRename();
      const settings = await getAiSliceSettings().catch(() => ({ ok: true as const, batchConcurrency: 4 }));
      const concurrency = Math.max(1, Math.min(8, Math.round(settings.batchConcurrency || 4)));
      let cursor = 0;
      const worker = async () => {
        while (cursor < pages.length) {
          const index = cursor;
          cursor += 1;
          const page = pages[index];
          if (!page) continue;
          const currentLabel = `P${index + 1}`;
          setAiProgress((current) => current ? {
            ...current,
            currentLabel,
            message: formatMessage(text.aiDetecting, { label: currentLabel })
          } : current);
          setStatus(formatMessage(text.aiBatchDetectingPage, { label: currentLabel, done: completed + failed, total: pages.length }));
          try {
            const response = await generateAiBoxes(projectId, page.id);
            mergeQueue = mergeQueue.catch(() => undefined).then(async () => {
              setAiProgress((current) => current ? {
                ...current,
                currentLabel,
                message: formatMessage(text.aiBatchPreparingPage, { label: currentLabel, done: completed + failed, total: pages.length })
              } : current);
              setStatus(formatMessage(text.aiBatchPreparingPage, { label: currentLabel, done: completed + failed, total: pages.length }));
              await wait(aiRevealDelayMs());
              workingPages = pagesRef.current;
              const latestPage = workingPages.find((item) => item.id === page.id);
              if (!latestPage) return;
              const merged = mergeAiBoxesIntoSlices({
                projectId,
                page: latestPage,
                boxes: response.boxes,
                cutMode: "rect",
                idSeed: `p${index + 1}_${Date.now().toString(36)}`
              });
              if (merged.addedCount) {
                const previousIds = new Set(latestPage.slices.map((slice) => slice.id));
                const addedIds = merged.slices.filter((slice) => !previousIds.has(slice.id)).map((slice) => slice.id);
                setPendingPreviewSliceIds((current) => new Set([...current, ...addedIds]));
                workingPages = workingPages.map((item) => item.id === page.id ? { ...item, slices: merged.slices } : item);
                pagesRef.current = workingPages;
                setPages(workingPages);
                await savePagesWithActive(workingPages, activePageIdRef.current);
              }
              completed += 1;
              addedTotal += merged.addedCount;
              skippedTotal += merged.skippedCount + response.diagnostics.rejectedBoxCount;
              setAiProgress((current) => current ? {
                ...current,
                completed,
                failed,
                added: addedTotal,
                skipped: skippedTotal,
                currentLabel,
                message: formatMessage(text.aiBatchDetection, { done: completed + failed, total: pages.length })
              } : current);
              setStatus(formatMessage(text.aiBatchAdded, { done: completed + failed, total: pages.length, added: addedTotal }));
            });
            await mergeQueue;
          } catch {
            failed += 1;
            setAiProgress((current) => current ? {
              ...current,
              completed,
              failed,
              currentLabel,
              message: formatMessage(text.aiBatchDetection, { done: completed + failed, total: pages.length })
            } : current);
          }
          setStatus(formatMessage(text.aiBatchAdded, { done: completed + failed, total: pages.length, added: addedTotal }));
        }
      };
      await Promise.all(Array.from({ length: Math.min(concurrency, pages.length) }, () => worker()));
      setAiProgress((current) => current ? {
        ...current,
        completed,
        failed,
        added: addedTotal,
        skipped: skippedTotal,
        currentLabel: "",
        message: formatMessage(text.aiBatchComplete, { completed, failed })
      } : current);
      setStatus(formatMessage(text.aiBatchCompleteStatus, { completed, failed, added: addedTotal, skipped: skippedTotal }));
    } catch (error) {
      setSaveState("error");
      setAiProgress((current) => current ? {
        ...current,
        message: formatMessage(text.aiBatchFailed, { error: getErrorMessage(error) })
      } : current);
      setStatus(formatMessage(text.aiBatchFailed, { error: getErrorMessage(error) }));
    } finally {
      setAiRunning(null);
    }
  }

  function updateAiProgress(patch: Partial<AiProgress>) {
    setAiProgress((current) => current ? { ...current, ...patch } : current);
  }

  function goToRelativePage(delta: number) {
    if (pageIndex < 0) return;
    const nextPage = pages[pageIndex + delta];
    if (!nextPage) return;
    setActivePageId(nextPage.id);
    selectSlice(null);
  }

  function selectSlice(sliceId: string | null, options: { additive?: boolean; range?: boolean } = {}) {
    setActiveSliceId(sliceId);
    if (!sliceId) {
      setSelectedSliceIds([]);
      return;
    }
    setSelectedSliceIds((current) => {
      if (!options.additive && !options.range) return [sliceId];
      if (options.range && activePage) {
        const anchorId = activeSliceId || current[current.length - 1] || sliceId;
        const from = activePage.slices.findIndex((slice) => slice.id === anchorId);
        const to = activePage.slices.findIndex((slice) => slice.id === sliceId);
        if (from >= 0 && to >= 0) {
          const [start, end] = from <= to ? [from, to] : [to, from];
          return activePage.slices.slice(start, end + 1).map((slice) => slice.id);
        }
      }
      return current.includes(sliceId) ? current.filter((id) => id !== sliceId) : [...current, sliceId];
    });
  }

  function focusActiveAssetName() {
    requestAnimationFrame(() => {
      activeNameInputRef.current?.focus();
      activeNameInputRef.current?.select();
    });
  }

  function centerStageOnSlice(slice: SliceRecord) {
    if (!activePage) return;
    setStagePosition({
      x: Math.round(stageSize.width / 2 - (slice.bbox.x + slice.bbox.width / 2) * scale),
      y: Math.round(stageSize.height / 2 - (slice.bbox.y + slice.bbox.height / 2) * scale)
    });
  }

  function selectSliceFromList(slice: SliceRecord, event?: { metaKey?: boolean; ctrlKey?: boolean; shiftKey?: boolean }) {
    selectSlice(slice.id, { additive: Boolean(event?.metaKey || event?.ctrlKey), range: Boolean(event?.shiftKey) });
    centerStageOnSlice(slice);
  }

  async function openAssetGallery() {
    if (!activePage) return;
    try {
      await flushPageRename();
      await saveNow();
      setGalleryOpen(true);
    } catch {
      return;
    }
  }

  function activateTool(nextTool: ToolMode) {
    setTool((currentTool) => currentTool === nextTool ? currentTool : nextTool);
  }

  function beginSliceEdit(sliceId: string, label = text.undoEditAsset) {
    if (sliceEditUndoRef.current === sliceId) return;
    pushUndo(label);
    sliceEditUndoRef.current = sliceId;
  }

  function commitSlicePatch(
    sliceId: string,
    patch: Partial<Pick<SliceRecord, "name" | "bbox" | "cutMode">>,
    undoLabel = text.undoEditAsset,
    options: { pushUndo?: boolean; saveImmediately?: boolean } = { pushUndo: true }
  ) {
    if (!activePage) return;
    const nextPages = pages.map((page) => page.id === activePage.id ? {
      ...page,
      slices: page.slices.map((slice) => slice.id === sliceId ? { ...slice, ...patch } : slice)
    } : page);
    scheduleSave(nextPages, { pushUndo: options.pushUndo, undoLabel });
    if (options.saveImmediately) {
      void saveNow(nextPages)
        .then(() => {
          setPreviewRevisionBySliceId((current) => ({
            ...current,
            [sliceId]: (current[sliceId] || 0) + 1
          }));
        })
        .catch(() => undefined);
    }
  }

  function applyPageCutMode(cutMode: CutMode) {
    setDefaultCutMode(cutMode);
    if (!activePage) return;
    if (!activePage.slices.length) {
      setStatus(formatMessage(text.newAssetsWillUseMode, { mode: cutModeLabel(cutMode, text) }));
      return;
    }
    if (activePage.slices.every((slice) => slice.cutMode === cutMode)) {
      setStatus(formatMessage(text.currentPageAlreadyMode, { mode: cutModeLabel(cutMode, text) }));
      return;
    }
    const nextPages = pages.map((page) => page.id === activePage.id ? {
      ...page,
      slices: page.slices.map((slice) => ({ ...slice, cutMode }))
    } : page);
    scheduleSave(nextPages, { pushUndo: true, undoLabel: text.undoChangePageCropMode });
  }

  function updateBoxColor(key: keyof typeof defaultBoxColors, value: string) {
    const nextColors = {
      ...boxColors,
      [key]: normalizeColor(value, defaultBoxColors[key])
    };
    setBoxColors(nextColors);
    window.localStorage.setItem(reviewColorStorageKey, JSON.stringify(nextColors));
  }

  function cycleSliceCutMode(current: CutMode): CutMode {
    if (current === "rect") return "subject";
    if (current === "subject") return "card";
    return "rect";
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
    selectSlice(null);
    scheduleSave(nextPages, { pushUndo: true, undoLabel: text.undoDeleteAsset });
  }

  function selectedIdsForActivePage(): string[] {
    if (!activePage) return [];
    const validIds = new Set(activePage.slices.map((slice) => slice.id));
    const selected = selectedSliceIds.filter((id) => validIds.has(id));
    if (selected.length) return selected;
    return activeSliceId && validIds.has(activeSliceId) ? [activeSliceId] : [];
  }

  function deleteSelectedSlices() {
    if (!activePage) return;
    const ids = selectedIdsForActivePage();
    if (!ids.length) return;
    const idSet = new Set(ids);
    const nextPages = pages.map((page) => page.id === activePage.id ? {
      ...page,
      slices: page.slices.filter((slice) => !idSet.has(slice.id)).map((slice, index) => ({ ...slice, sliceIndex: index + 1 }))
    } : page);
    selectSlice(null);
    scheduleSave(nextPages, { pushUndo: true, undoLabel: ids.length > 1 ? text.undoDeleteAssets : text.undoDeleteAsset });
  }

  function copySelectedSlices() {
    if (!activePage) return;
    const idSet = new Set(selectedIdsForActivePage());
    const copied = activePage.slices.filter((slice) => idSet.has(slice.id)).map((slice) => ({ ...slice, bbox: { ...slice.bbox } }));
    if (!copied.length) return;
    copiedSlicesRef.current = copied;
    setStatus(formatMessage(text.copiedAssets, { count: copied.length }));
  }

  function pasteCopiedSlices() {
    if (!activePage || !copiedSlicesRef.current.length) return;
    const offset = 12;
    const existingCount = activePage.slices.length;
    const pasted = copiedSlicesRef.current.map((slice, index): SliceRecord => ({
      ...slice,
      id: `${activePage.id}__slice_${Date.now().toString(36)}_paste_${index + 1}`,
      projectId,
      pageId: activePage.id,
      sliceIndex: existingCount + index + 1,
      name: nextCopyName(slice.name),
      bbox: normalizeBox({
        ...slice.bbox,
        x: slice.bbox.x + offset,
        y: slice.bbox.y + offset
      }, activePage),
      selected: true
    }));
    const pastedIds = pasted.map((slice) => slice.id);
    const nextPages = pages.map((page) => page.id === activePage.id ? { ...page, slices: [...page.slices, ...pasted] } : page);
    setActiveSliceId(pastedIds[pastedIds.length - 1] || null);
    setSelectedSliceIds(pastedIds);
    setPendingPreviewSliceIds((current) => new Set([...current, ...pastedIds]));
    scheduleSave(nextPages, { pushUndo: true, undoLabel: text.undoPasteAssets });
    setStatus(formatMessage(text.pastedAssets, { count: pasted.length }));
  }

  function nudgeSelectedSlices(delta: Point) {
    if (!activePage) return;
    const ids = selectedIdsForActivePage();
    if (!ids.length) return;
    const idSet = new Set(ids);
    const nextPages = pages.map((page) => page.id === activePage.id ? {
      ...page,
      slices: page.slices.map((slice) => idSet.has(slice.id) ? {
        ...slice,
        bbox: normalizeBox({
          ...slice.bbox,
          x: slice.bbox.x + delta.x,
          y: slice.bbox.y + delta.y
        }, activePage)
      } : slice)
    } : page);
    scheduleSave(nextPages, { pushUndo: true, undoLabel: text.undoMoveAssets });
    setStatus(formatMessage(text.movedAssets, { count: ids.length }));
  }

  function snapMovedBoxToGuides(box: BBox, page: WorkbenchPage, movingSliceId: string): BBox {
    const normalized = normalizeBox(box, page);
    const verticalGuides = [0, page.width];
    const horizontalGuides = [0, page.height];
    for (const slice of page.slices) {
      if (slice.id === movingSliceId) continue;
      verticalGuides.push(slice.bbox.x, slice.bbox.x + slice.bbox.width);
      horizontalGuides.push(slice.bbox.y, slice.bbox.y + slice.bbox.height);
    }

    const leftSnap = nearestGuide(normalized.x, verticalGuides);
    const rightSnap = nearestGuide(normalized.x + normalized.width, verticalGuides);
    const topSnap = nearestGuide(normalized.y, horizontalGuides);
    const bottomSnap = nearestGuide(normalized.y + normalized.height, horizontalGuides);

    let x = normalized.x;
    let y = normalized.y;
    if (leftSnap !== null) {
      x = leftSnap;
    } else if (rightSnap !== null) {
      x = rightSnap - normalized.width;
    }
    if (topSnap !== null) {
      y = topSnap;
    } else if (bottomSnap !== null) {
      y = bottomSnap - normalized.height;
    }

    return normalizeBox({ ...normalized, x, y }, page);
  }

  function snapResizedBoxToGuides(box: BBox, page: WorkbenchPage, movingSliceId: string): BBox {
    const normalized = normalizeBox(box, page, 8);
    const verticalGuides = [0, page.width];
    const horizontalGuides = [0, page.height];
    for (const slice of page.slices) {
      if (slice.id === movingSliceId) continue;
      verticalGuides.push(slice.bbox.x, slice.bbox.x + slice.bbox.width);
      horizontalGuides.push(slice.bbox.y, slice.bbox.y + slice.bbox.height);
    }

    let left = normalized.x;
    let right = normalized.x + normalized.width;
    let top = normalized.y;
    let bottom = normalized.y + normalized.height;
    const leftSnap = nearestGuide(left, verticalGuides);
    const rightSnap = nearestGuide(right, verticalGuides);
    const topSnap = nearestGuide(top, horizontalGuides);
    const bottomSnap = nearestGuide(bottom, horizontalGuides);

    if (leftSnap !== null && right - leftSnap >= 8) left = leftSnap;
    if (rightSnap !== null && rightSnap - left >= 8) right = rightSnap;
    if (topSnap !== null && bottom - topSnap >= 8) top = topSnap;
    if (bottomSnap !== null && bottomSnap - top >= 8) bottom = bottomSnap;

    return normalizeBox({ x: left, y: top, width: right - left, height: bottom - top }, page, 8);
  }

  function onTransformEnd(slice: SliceRecord, node: Konva.Rect) {
    if (!activePage) return;
    selectSlice(slice.id);
    const scaleX = node.scaleX();
    const scaleY = node.scaleY();
    node.scaleX(1);
    node.scaleY(1);
    const resizedBox = normalizeBox({
        x: node.x(),
        y: node.y(),
        width: Math.max(1, node.width() * scaleX),
        height: Math.max(1, node.height() * scaleY)
      }, activePage);
    commitSlicePatch(slice.id, {
      bbox: snapResizedBoxToGuides(resizedBox, activePage, slice.id)
    }, text.undoResizeAsset);
  }

  async function commitPageOrder(nextPages: WorkbenchPage[], activePageIdAfterOrder = activePageId) {
    if (nextPages.map((page) => page.id).join("|") === pages.map((page) => page.id).join("|")) return;
    setSaveState("saving");
    try {
      await flushPageRename();
      await saveNow();
      pushUndo(text.undoReorderPages);
      setPages(nextPages);
      const projectDetail = await reorderPages(projectId, nextPages.map((page) => page.id));
      await applyProjectDetail(projectDetail, activePageIdAfterOrder, activeSliceId);
      setSaveState("saved");
      setStatus(text.pageOrderSaved);
    } catch (error) {
      setSaveState("error");
      setStatus(formatMessage(text.pageReorderFailed, { error: getErrorMessage(error) }));
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
      pushUndo(pageConfirmAction.type === "delete" ? text.undoDeletePage : text.undoReplacePage, { sourceFileAction: true });
      delete imageLoadRef.current[pageConfirmAction.pageId];
      const projectDetail = pageConfirmAction.type === "delete"
        ? await deletePage(projectId, pageConfirmAction.pageId)
        : await replacePage(projectId, pageConfirmAction.pageId, pageConfirmAction.file);
      if (pageConfirmAction.type === "replace") {
        setPageThumbnailRevisionById((current) => ({
          ...current,
          [pageConfirmAction.pageId]: (current[pageConfirmAction.pageId] || 0) + 1
        }));
      }
      await applyProjectDetail(
        projectDetail,
        pageConfirmAction.type === "replace" ? pageConfirmAction.pageId : null,
        null,
        pageConfirmAction.type === "replace" ? new Set([pageConfirmAction.pageId]) : new Set()
      );
      setSaveState("saved");
      setStatus(pageConfirmAction.type === "delete" ? text.pageDeleted : text.pageReplaced);
      setPageConfirmAction(null);
    } catch (error) {
      setSaveState("error");
      setStatus(formatMessage(text.pageActionFailed, {
        action: pageConfirmAction.type === "delete" ? text.delete : text.replace,
        error: getErrorMessage(error)
      }));
    }
  }

  function commitActiveSliceBbox(patch: Partial<BBox>) {
    if (!activePage || !activeSlice) return;
    commitSlicePatch(activeSlice.id, {
      bbox: normalizeBox({ ...activeSlice.bbox, ...patch }, activePage)
    }, text.undoEditBbox);
  }

  function updateBboxDraft(field: BBoxField, value: string) {
    setBboxDraft((current) => ({ ...current, [field]: value }));
  }

  function commitBboxDraft() {
    if (!activePage || !activeSlice) return;
    const parsed = {
      x: Number(bboxDraft.x),
      y: Number(bboxDraft.y),
      width: Number(bboxDraft.width),
      height: Number(bboxDraft.height)
    };
    if (!Number.isFinite(parsed.x) || !Number.isFinite(parsed.y) || !Number.isFinite(parsed.width) || !Number.isFinite(parsed.height)) {
      setBboxDraft({
        x: String(activeSlice.bbox.x),
        y: String(activeSlice.bbox.y),
        width: String(activeSlice.bbox.width),
        height: String(activeSlice.bbox.height)
      });
      return;
    }
    commitActiveSliceBbox({
      x: clamp(parsed.x, 0, activePage.width - 1),
      y: clamp(parsed.y, 0, activePage.height - 1),
      width: Math.max(1, parsed.width),
      height: Math.max(1, parsed.height)
    });
  }

  function onBboxInputKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.currentTarget.blur();
      return;
    }
    if (event.key === "Escape" && activeSlice) {
      setBboxDraft({
        x: String(activeSlice.bbox.x),
        y: String(activeSlice.bbox.y),
        width: String(activeSlice.bbox.width),
        height: String(activeSlice.bbox.height)
      });
      event.currentTarget.blur();
    }
  }

  const draftBox = useMemo(() => {
    if (!drag || drag.type !== "draw" || !activePage) return null;
    return draftToBox(drag.start, drag.current, activePage);
  }, [drag, activePage]);

  return (
    <main className={`reviewShell ${inspectorCollapsed ? "inspectorCollapsed" : ""} ${assetListCollapsed ? "assetListCollapsed" : ""}`}>
      <header className="reviewTopbar">
        <div className="topbarProject">
          <a className="topbarBrand" href="/projects" aria-label={text.backToProjects}>
            Slice Studio
          </a>
          <div className="projectTitleBlock">
            <strong>{text.reviewWorkbench}</strong>
            <span>{detail?.project.name || text.untitledProject}</span>
          </div>
        </div>
        <div className="topbarActions">
          <label className="toolbarButton uploadButton">
            <Upload aria-hidden="true" />
            <span>{text.upload}</span>
            <input id="pageUpload" name="pageUpload" type="file" multiple accept="image/*" onChange={(event) => void handleUpload(event.target.files)} />
          </label>
          <button className="toolbarButton" type="button" disabled={!undoStack.length} title={undoStack.length ? `${text.undo}: ${undoStack[undoStack.length - 1].label}` : text.nothingToUndo} onClick={() => void restoreUndo()}>
            <RotateCcw aria-hidden="true" />
            <span>{text.undo}</span>
          </button>
          <button className="toolbarButton ghostButton" type="button" disabled title={text.redoUnavailable}>
            <span>{text.redo}</span>
          </button>
          <div className="zoomGroup" aria-label={text.zoomControls}>
            <button className="zoomButton" type="button" onClick={fitPage}>{text.fit}</button>
            <button className="zoomIconButton" type="button" aria-label={text.zoomOut} onClick={() => setScale((value) => Math.max(0.08, value - 0.1))}>
              <Minus aria-hidden="true" />
            </button>
            <span className="zoomReadout">{Math.round(scale * 100)}%</span>
            <button className="zoomIconButton" type="button" aria-label={text.zoomIn} onClick={() => setScale((value) => Math.min(4, value + 0.1))}>
              <Plus aria-hidden="true" />
            </button>
          </div>
          <button className="toolbarButton aiButton" type="button" disabled={!activePage || aiBusy} onClick={() => void runAiForCurrentPage()}>
            <Sparkles aria-hidden="true" />
            <span>{aiRunning === "page" ? text.aiRunning : text.aiCurrent}</span>
          </button>
          <button className="toolbarButton aiButton" type="button" disabled={!pages.length || aiBusy} onClick={() => void runAiForAllPages()}>
            <Bot aria-hidden="true" />
            <span>{aiRunning === "batch" ? text.batchRunning : text.aiAll}</span>
          </button>
          <button className="toolbarButton exportButton" type="button" disabled={!hasSlices || exportBusy} onClick={() => void exportAssets()}>
            <Download aria-hidden="true" />
            <span>{exportTarget === "assets" ? text.exporting : text.assetsZip}</span>
          </button>
          <button className="toolbarButton exportButton" type="button" disabled={!activePage || exportBusy} onClick={() => void exportCurrentPage()}>
            <Download aria-hidden="true" />
            <span>{exportTarget === "page" ? text.exporting : text.pageZip}</span>
          </button>
          <button className="toolbarButton exportButton" type="button" disabled={!hasSlices || exportBusy} onClick={() => void exportProject()}>
            <Download aria-hidden="true" />
            <span>{exportTarget === "project" ? text.exporting : text.projectZip}</span>
          </button>
          <div className="languageToggle" role="group" aria-label={text.language}>
            <button type="button" className={language === "zh" ? "active" : ""} aria-pressed={language === "zh"} title={text.chinese} onClick={() => changeLanguage("zh")}>中</button>
            <button type="button" className={language === "en" ? "active" : ""} aria-pressed={language === "en"} title={text.english} onClick={() => changeLanguage("en")}>EN</button>
          </div>
          <span className={`saveState ${saveState}`} title={status}>{saveLabel}</span>
          {saveState === "error" ? (
            <button className="toolbarButton ghostButton" type="button" title={text.unsavedEditsHeld} onClick={() => void saveNow().catch(() => undefined)}>
              <span>{text.retrySave}</span>
            </button>
          ) : null}
        </div>
      </header>

      <aside className="pageRail" aria-label={text.pages}>
        <div className="pageRailHeader">
          <span>{text.pages} ({pages.length})</span>
          <Search aria-hidden="true" />
        </div>
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
                aria-label={`${text.dragToReorder} P${index + 1}`}
                title={text.dragToReorder}
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
                selectSlice(null);
              }}>
                <span className="pageThumbOrdinal">{index + 1}</span>
                <span className="pageThumbImage">
                  <img src={apiUrl(withClientRevision(page.thumbnailUrl, pageThumbnailRevisionById[page.id] || 0))} alt="" loading="lazy" />
                </span>
                <span className="pageThumbBody">
                  <span className="pageThumbName">{page.displayName || page.originalName}</span>
                  <span className="pageThumbMeta">{page.width}x{page.height}</span>
                </span>
                <span className="pageThumbAssets">{page.slices.length} {text.assets}</span>
                <span className={`pageThumbStatus ${pageStatusClass(page, page.id === activePageId)}`}>{pageStatusLabel(page, page.id === activePageId, text)}</span>
              </button>
            </div>
          ))}
          {!pages.length && (
            <div className="pageRailEmpty">
              <Images aria-hidden="true" />
              <span>{text.noPages}</span>
            </div>
          )}
        </div>
        <footer className="pageRailFooter">
          <span>{text.project}: {detail?.project.name || text.untitled}</span>
          <span>{pages.length} {text.pages}</span>
        </footer>
      </aside>

      <section className="stageArea">
        <div className="canvasToolRail" role="group" aria-label={text.canvasTools}>
          <button className={tool === "select" ? "active" : ""} type="button" title={text.select} aria-label={text.selectTool} aria-pressed={tool === "select"} onClick={() => activateTool("select")}>
            <MousePointer2 aria-hidden="true" />
          </button>
          <button className={tool === "draw" ? "active" : ""} type="button" title={text.draw} aria-label={text.drawTool} aria-pressed={tool === "draw"} onClick={() => activateTool("draw")}>
            <Square aria-hidden="true" />
          </button>
          <button className={tool === "pan" ? "active" : ""} type="button" title={text.pan} aria-label={text.panTool} aria-pressed={tool === "pan"} onClick={() => activateTool("pan")}>
            <Hand aria-hidden="true" />
          </button>
        </div>
        <div ref={stageWrapRef} className="stageWrap">
          {!activePage && <div className="canvasHint">{text.uploadHint}</div>}
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
                  const isSelected = selectedSliceIds.includes(slice.id);
                  return (
                    <Rect
                      key={slice.id}
                      ref={(node) => {
                        sliceNodeRefs.current[slice.id] = node;
                      }}
                      sliceId={slice.id}
                      x={slice.bbox.x}
                      y={slice.bbox.y}
                      width={slice.bbox.width}
                      height={slice.bbox.height}
                      stroke={isActive ? boxColors.active : boxColors.slice}
                      strokeWidth={isActive || isSelected ? 2 : 1.4}
                      fill={colorWithAlpha(boxColors.slice, tool === "draw" ? 0.02 : 0.08)}
                      draggable={tool === "select"}
                      listening={tool === "select"}
                      onMouseDown={(event) => {
                        if (tool !== "select") return;
                        event.cancelBubble = true;
                        selectSlice(slice.id, { additive: event.evt.metaKey || event.evt.ctrlKey, range: event.evt.shiftKey });
                      }}
                      onDragStart={() => {
                        if (tool === "select") selectSlice(slice.id);
                      }}
                      onDragEnd={(event) => {
                        selectSlice(slice.id);
                        const movedBox = normalizeBox({ ...slice.bbox, x: event.target.x(), y: event.target.y() }, activePage);
                        commitSlicePatch(slice.id, { bbox: snapMovedBoxToGuides(movedBox, activePage, slice.id) }, text.undoMoveAsset);
                      }}
                      onTransformEnd={(event) => onTransformEnd(slice, event.target as Konva.Rect)}
                    />
                  );
                })}
                {tool === "select" && activeSlice && (
                  <Transformer
                    ref={transformerRef}
                    rotateEnabled={false}
                    enabledAnchors={transformerAnchors}
                    onMouseDown={(event) => {
                      event.cancelBubble = true;
                    }}
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
        {activePage ? (
          <footer className="stageFooter">
            <span>{activePage.width}x{activePage.height}</span>
            <span>{Math.round(scale * 100)}%</span>
            <span className={`stageStatus ${saveState}`}>{status}</span>
          </footer>
        ) : null}
      </section>

      <aside className={`assetInspector ${assetListCollapsed ? "assetListCollapsed" : ""}`} aria-label={text.assetInspector}>
        <button className="inspectorToggle" type="button" aria-label={inspectorCollapsed ? text.expandInspector : text.collapseInspector} title={inspectorCollapsed ? text.expandInspector : text.collapseInspector} onClick={() => setInspectorCollapsed((value) => !value)}>
          {inspectorCollapsed ? <PanelRightOpen aria-hidden="true" /> : <PanelRightClose aria-hidden="true" />}
        </button>
        {!inspectorCollapsed && (
          <div className="inspectorInner">
            <section className="assetReviewPanel">
              <header className="inspectorHeader">
                <div>
                  <h2>{text.assets} ({activePageAssetCount})</h2>
                  <span>{visibleAssets.length} {text.visible}</span>
                </div>
                <button className="assetPanelCollapseButton" type="button" aria-label={assetListCollapsed ? text.expandAssetsList : text.collapseAssetsList} title={assetListCollapsed ? text.expandAssetsList : text.collapseAssetsList} onClick={() => setAssetListCollapsed((value) => !value)}>
                  {assetListCollapsed ? <ChevronDown aria-hidden="true" /> : <ChevronUp aria-hidden="true" />}
                </button>
              </header>
              {!assetListCollapsed ? (
                <>
                  <div className="assetSearchRow">
                    <label>
                      <Search aria-hidden="true" />
                      <input
                        value={assetSearch}
                        onChange={(event) => setAssetSearch(event.target.value)}
                        placeholder={text.searchAssetsPlaceholder}
                        aria-label={text.searchAssets}
                      />
                    </label>
                    <select aria-label={text.filterByCropMode} value={assetCutModeFilter} onChange={(event) => setAssetCutModeFilter(event.target.value as "all" | CutMode)}>
                      <option value="all">{text.allModes}</option>
                      <option value="rect">{text.rect}</option>
                      <option value="subject">{text.subject}</option>
                      <option value="card">{text.innerImage}</option>
                    </select>
                    <select aria-label={text.sortAssets} value={assetSort} onChange={(event) => setAssetSort(event.target.value as "order" | "name" | "size")}>
                      <option value="order">{text.order}</option>
                      <option value="name">{text.name}</option>
                      <option value="size">{text.size}</option>
                    </select>
                  </div>
                  <div className="assetList">
                    {visibleAssets.map((slice, index) => (
                      <div
                        key={slice.id}
                        className={`assetItem ${slice.id === activeSliceId ? "active" : ""} ${selectedSliceIds.includes(slice.id) ? "selected" : ""}`}
                        ref={(node) => {
                          assetItemRefs.current[slice.id] = node;
                        }}
                        onClick={(event) => selectSliceFromList(slice, event)}
                      >
                        <button type="button" className="assetPreviewButton" aria-label={formatMessage(text.selectAsset, { name: slice.name })} onClick={(event) => {
                          event.stopPropagation();
                          selectSliceFromList(slice, event);
                        }}>
                          {pendingPreviewSliceIds.has(slice.id) ? (
                            <span className="assetPreviewPlaceholder" aria-hidden="true">…</span>
                          ) : (
                            <img src={slicePreviewUrl(projectId, slice, previewRevisionBySliceId[slice.id] || 0)} alt="" draggable={false} />
                          )}
                        </button>
                        <span className="assetFields">
                          <input
                            name={`sliceName-${slice.id}`}
                            aria-label={text.assetName}
                            value={slice.name}
                            onFocus={() => {
                              selectSlice(slice.id);
                              beginSliceEdit(slice.id, text.undoEditAsset);
                            }}
                            onBlur={() => {
                              sliceEditUndoRef.current = null;
                            }}
                            onClick={(event) => event.stopPropagation()}
                            onChange={(event) => commitSlicePatch(slice.id, { name: event.target.value }, text.undoEditAsset, { pushUndo: false })}
                          />
                          <small>{slice.bbox.width}x{slice.bbox.height}</small>
                        </span>
                        <button
                          className={`assetCutModeButton ${slice.cutMode}`}
                          type="button"
                          aria-label={formatMessage(text.assetCropMode, { name: slice.name, mode: cutModeLabel(slice.cutMode, text) })}
                          title={text.cycleCropMode}
                          onClick={(event) => {
                            event.stopPropagation();
                            selectSlice(slice.id);
                            commitSlicePatch(slice.id, { cutMode: cycleSliceCutMode(slice.cutMode) }, text.undoChangeCropMode);
                          }}
                        >
                          {cutModeLabel(slice.cutMode, text)}
                        </button>
                        <button className="assetItemDelete" type="button" aria-label={`${text.deleteAsset}: ${slice.name}`} title={text.deleteAsset} onClick={(event) => {
                          event.stopPropagation();
                          deleteActiveSlice(slice.id);
                        }}>
                          <Trash2 aria-hidden="true" />
                        </button>
                      </div>
                    ))}
                    {activePage && !visibleAssets.length ? (
                      <div className="assetListEmpty">
                        <Images aria-hidden="true" />
                        <span>{text.noAssetsMatch}</span>
                      </div>
                    ) : null}
                  </div>
                </>
              ) : null}
            </section>
            <section className="detailsPanel">
              <header className="detailsHeader">
                <div>
                  <h2>{text.details}</h2>
                  <span>{activeSlice ? activeSlice.name : text.noAssetSelected}</span>
                </div>
                <button className="assetGalleryButton" type="button" disabled={!activePage} onClick={() => void openAssetGallery()}>
                  <Grid2X2 aria-hidden="true" />
                  <span>{text.overview}</span>
                </button>
              </header>
              <section className="cutModePanel">
                <div className="cutModePanelHeader">
                  <strong>{text.pageCropMode}</strong>
                  <span>{pageCutMode === "mixed" ? text.mixed : cutModeLabel(pageCutMode, text)}</span>
                </div>
                <div className="cutModeSegmented" role="group" aria-label={text.pageCropModeAria}>
                  {(["rect", "subject", "card"] as CutMode[]).map((mode) => (
                    <button
                      key={mode}
                      type="button"
                      className={pageCutMode === mode ? "active" : ""}
                      aria-pressed={pageCutMode === mode}
                      onClick={() => applyPageCutMode(mode)}
                    >
                      {cutModeLabel(mode, text)}
                    </button>
                  ))}
                </div>
              </section>
              <section className="pageInfoPanel">
                <div className="pageInfoHeader">
                  <strong>{activePage ? `P${pageIndex + 1}` : text.noPage}</strong>
                  <span>{activePage ? `${activePage.width}x${activePage.height}` : text.noPage}</span>
                </div>
                {activePage ? (
                  <label className="pageNameField">
                    <span>{text.pageName}</span>
                    <input
                      name={`pageName-${activePage.id}`}
                      aria-label={text.pageName}
                      placeholder={`${text.page} ${pageIndex + 1}`}
                      value={activePage.displayName}
                      onChange={(event) => commitPageName(activePage.id, event.target.value)}
                    />
                  </label>
                ) : null}
                <span>{activePage ? activePage.originalName : text.uploadHint}</span>
                {activePage ? (
                  <div className="pageActionGrid">
                    <button type="button" onClick={() => replaceInputRef.current?.click()}>
                      <Upload aria-hidden="true" />
                      {text.replace}
                    </button>
                    <button type="button" className="dangerButton" onClick={() => setPageConfirmAction({ type: "delete", pageId: activePage.id })}>
                      <Trash2 aria-hidden="true" />
                      {text.delete}
                    </button>
                  </div>
                ) : null}
              </section>
              <section className="boxColorPanel">
                <div className="boxColorHeader">
                  <strong>{text.boxColor}</strong>
                  <button type="button" onClick={resetBoxColors}>{text.reset}</button>
                </div>
                <div className="boxColorFields">
                  <label>
                    <span>{text.normal}</span>
                    <input type="color" value={boxColors.slice} onChange={(event) => updateBoxColor("slice", event.target.value)} aria-label={text.normalBoxColor} />
                  </label>
                  <label>
                    <span>{text.active}</span>
                    <input type="color" value={boxColors.active} onChange={(event) => updateBoxColor("active", event.target.value)} aria-label={text.activeBoxColor} />
                  </label>
                </div>
              </section>
              {activeSlice ? (
                <section className="activeAssetPanel">
                  <div className="activeAssetHeader">
                    <div>
                      <span>{text.activeAsset}</span>
                      <strong>{activeSlice.name || text.untitled}</strong>
                    </div>
                    <button className="assetDangerButton" type="button" aria-label={text.deleteCurrentAsset} title={text.deleteCurrentAsset} onClick={() => deleteSelectedSlices()}>
                      <Trash2 aria-hidden="true" />
                    </button>
                  </div>
                  <div className="activeAssetEditRow">
                    <input
                      ref={activeNameInputRef}
                      name={`activeSliceName-${activeSlice.id}`}
                      aria-label={text.assetName}
                      value={activeSlice.name}
                      onFocus={() => beginSliceEdit(activeSlice.id, text.undoEditAsset)}
                      onBlur={() => {
                        sliceEditUndoRef.current = null;
                      }}
                      onChange={(event) => commitSlicePatch(activeSlice.id, { name: event.target.value }, text.undoEditAsset, { pushUndo: false })}
                    />
                    <span>{activeSlice.bbox.width}x{activeSlice.bbox.height}</span>
                  </div>
                  <div className="detailsGrid">
                    <label>
                      <span>X</span>
                      <input type="number" value={bboxDraft.x} onChange={(event) => updateBboxDraft("x", event.target.value)} onBlur={commitBboxDraft} onKeyDown={onBboxInputKeyDown} />
                    </label>
                    <label>
                      <span>Y</span>
                      <input type="number" value={bboxDraft.y} onChange={(event) => updateBboxDraft("y", event.target.value)} onBlur={commitBboxDraft} onKeyDown={onBboxInputKeyDown} />
                    </label>
                    <label>
                      <span>W</span>
                      <input type="number" min={1} value={bboxDraft.width} onChange={(event) => updateBboxDraft("width", event.target.value)} onBlur={commitBboxDraft} onKeyDown={onBboxInputKeyDown} />
                    </label>
                    <label>
                      <span>H</span>
                      <input type="number" min={1} value={bboxDraft.height} onChange={(event) => updateBboxDraft("height", event.target.value)} onBlur={commitBboxDraft} onKeyDown={onBboxInputKeyDown} />
                    </label>
                  </div>
                  <label className="detailsSelectRow">
                    <span>{text.cropMode}</span>
                    <select value={activeSlice.cutMode} onChange={(event) => commitSlicePatch(activeSlice.id, { cutMode: event.target.value as CutMode }, text.undoChangeCropMode, { saveImmediately: true })}>
                      <option value="rect">{text.rect}</option>
                      <option value="subject">{text.subject}</option>
                      <option value="card">{text.innerImage}</option>
                    </select>
                  </label>
                  <div className="detailsStaticGrid">
                    <span>{text.page}</span>
                    <strong>{activePage ? `${pageIndex + 1}/${pages.length}` : "-"}</strong>
                    <span>{text.format}</span>
                    <strong>PNG</strong>
                    <span>{text.boxColor}</span>
                    <strong>{boxColors.slice}</strong>
                    <span>{text.locked}</span>
                    <button type="button" disabled title={text.lockedMissingInterface}>
                      <Lock aria-hidden="true" />
                      {text.off}
                    </button>
                  </div>
                  <button className="deleteAssetWideButton" type="button" onClick={() => deleteSelectedSlices()}>
                    {selectedIdsForActivePage().length > 1 ? text.deleteSelectedAssets : text.deleteAsset}
                  </button>
                </section>
              ) : (
                <section className="inspectorSummary">
                  <span>{activePage ? `${activePageAssetCount} ${text.assets} · ${totalAssets} ${text.total}` : text.pageStartHint}</span>
                  {activePageAssetCount === 0 && (
                    <span>{activePage ? text.createAssetHint : text.canvasReadyHint}</span>
                  )}
                </section>
              )}
            </section>
          </div>
        )}
      </aside>
      <input ref={replaceInputRef} className="hiddenFileInput" type="file" accept="image/*" onChange={(event) => requestReplaceActivePage(event.target.files)} />
      {aiProgress && !aiProgress.hidden ? (
        <section className={`aiProgressPanel ${aiProgress.minimized ? "minimized" : ""}`} aria-label={text.aiDetectionProgress} aria-live="polite">
          <header className="aiProgressHeader">
            <div>
              <strong>{aiProgress.mode === "batch" ? text.aiBatchProcessingRunning : text.aiCurrentPage}</strong>
              <span>{aiProgress.message}</span>
            </div>
            <div className="aiProgressActions">
              <button type="button" aria-label={aiProgress.minimized ? text.expandAiProgress : text.minimizeAiProgress} title={aiProgress.minimized ? text.expand : text.minimize} onClick={() => updateAiProgress({ minimized: !aiProgress.minimized })}>
                <GripHorizontal aria-hidden="true" />
              </button>
              <button type="button" aria-label={text.hideAiProgress} title={text.hide} onClick={() => updateAiProgress({ hidden: true })}>
                <X aria-hidden="true" />
              </button>
            </div>
          </header>
          <div className="aiProgressTrack" aria-hidden="true">
            <span style={{ width: `${aiProgressPercent(aiProgress)}%` }} />
          </div>
          {!aiProgress.minimized ? (
            <div className="aiProgressStats">
              <span><strong>{aiProgress.completed + aiProgress.failed}/{aiProgress.total}</strong> {text.total}</span>
              <span><strong>{aiProgress.completed}</strong> {text.completed}</span>
              <span><strong>{aiProgress.added}</strong> {text.newAssets}</span>
              <span><strong>{aiProgress.skipped}</strong> {text.skipped}</span>
              <span><strong>{aiProgress.failed}</strong> {text.failed}</span>
            </div>
          ) : null}
        </section>
      ) : null}
      {pageConfirmAction ? (
        <div className="modalBackdrop" role="presentation" onMouseDown={() => setPageConfirmAction(null)}>
          <section
            className="confirmDialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="page-action-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <button type="button" className="dialogCloseButton" aria-label={text.close} onClick={() => setPageConfirmAction(null)}>
              <X aria-hidden="true" />
            </button>
            <div className={`dialogIcon ${pageConfirmAction.type === "delete" ? "danger" : "primary"}`}>
              {pageConfirmAction.type === "delete" ? <Trash2 aria-hidden="true" /> : <Upload aria-hidden="true" />}
            </div>
            <div className="dialogText">
              <h2 id="page-action-title">{pageConfirmAction.type === "delete" ? text.deleteCurrentPageQuestion : text.replaceCurrentPageQuestion}</h2>
              <p>
                {pageConfirmAction.type === "delete"
                  ? text.deleteCurrentPageDescription
                  : formatMessage(text.replaceCurrentPageDescription, { file: pageConfirmAction.file.name })}
              </p>
            </div>
            <div className="dialogActions">
              <button type="button" onClick={() => setPageConfirmAction(null)}>{text.cancel}</button>
              <button type="button" className={pageConfirmAction.type === "delete" ? "dangerConfirmButton" : "primaryConfirmButton"} onClick={() => void confirmPageAction()}>
                {pageConfirmAction.type === "delete" ? text.confirmDelete : text.confirmReplace}
              </button>
            </div>
          </section>
        </div>
      ) : null}
      {galleryOpen && activePage ? (
        <div className="modalBackdrop assetGalleryBackdrop" role="presentation" onMouseDown={() => setGalleryOpen(false)}>
          <section
            className="assetGalleryDialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="asset-gallery-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <header className="assetGalleryHeader">
              <div>
                <h2 id="asset-gallery-title">{text.assetOverview}</h2>
                <span>P{pageIndex + 1} · {activePage.slices.length} {text.assets} · {text.clickCardToLocate}</span>
              </div>
              <div className="assetGalleryPageNav" aria-label={text.assetOverviewPagination}>
                <button type="button" title={text.previousPage} aria-label={text.previousPage} disabled={pageIndex <= 0} onClick={() => goToRelativePage(-1)}>
                  <ChevronLeft aria-hidden="true" />
                </button>
                <span>{pageIndex + 1}/{pages.length}</span>
                <button type="button" title={text.nextPage} aria-label={text.nextPage} disabled={pageIndex >= pages.length - 1} onClick={() => goToRelativePage(1)}>
                  <ChevronRight aria-hidden="true" />
                </button>
              </div>
              <button type="button" className="dialogCloseButton" aria-label={text.closeAssetOverview} onClick={() => setGalleryOpen(false)}>
                <X aria-hidden="true" />
              </button>
            </header>
            <div className="assetGalleryGrid">
              {!activePage.slices.length ? (
                <div className="assetGalleryEmpty">
                  <Grid2X2 aria-hidden="true" />
                  <span>{text.noAssetsOnPage}</span>
                </div>
              ) : activePage.slices.map((slice, index) => {
                const isActive = slice.id === activeSliceId;
                return (
                  <article
                    key={slice.id}
                    className={`assetGalleryCard ${isActive ? "active" : ""}`}
                  >
                    <span className="assetGalleryCardHeader">
                      <strong>#{index + 1}</strong>
                      <span>{slice.bbox.width}x{slice.bbox.height}</span>
                    </span>
                    <button
                      type="button"
                      className="assetGalleryPreview"
                      onClick={() => {
                        selectSliceFromList(slice);
                        setGalleryOpen(false);
                      }}
                    >
                      {pendingPreviewSliceIds.has(slice.id) ? (
                        <span className="assetGalleryPreviewPlaceholder" aria-hidden="true">…</span>
                      ) : (
                        <img src={slicePreviewUrl(projectId, slice, previewRevisionBySliceId[slice.id] || 0)} alt="" draggable={false} />
                      )}
                    </button>
                    <span className="assetGalleryCutModes" role="group" aria-label={formatMessage(text.assetCropMode, { name: slice.name, mode: cutModeLabel(slice.cutMode, text) })}>
                      {(["rect", "subject", "card"] as CutMode[]).map((mode) => (
                        <button
                          key={mode}
                          type="button"
                          className={`assetGalleryCutMode ${slice.cutMode === mode ? "active" : ""}`}
                          aria-pressed={slice.cutMode === mode}
                          onClick={(event) => {
                            event.stopPropagation();
                            selectSlice(slice.id);
                            if (slice.cutMode !== mode) commitSlicePatch(slice.id, { cutMode: mode }, text.undoChangeCropMode, { saveImmediately: true });
                          }}
                        >
                          {cutModeLabel(mode, text)}
                        </button>
                      ))}
                    </span>
                    <span className="assetGalleryMeta">
                      <strong>{slice.name}</strong>
                      <span>{cutModeLabel(slice.cutMode, text)}</span>
                    </span>
                  </article>
                );
              })}
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

function slicePreviewUrl(projectId: string, slice: SliceRecord, previewRevision: number): string {
  const box = slice.bbox;
  const version = [slice.cutMode, box.x, box.y, box.width, box.height, slice.name, previewRevision].join("-");
  return apiUrl(`/api/projects/${projectId}/slices/${encodeURIComponent(slice.id)}/preview.png?v=${encodeURIComponent(version)}`);
}

function cutModeLabel(mode: CutMode, text: ReviewText): string {
  if (mode === "subject") return text.subject;
  if (mode === "card") return text.innerImage;
  return text.rect;
}

function sliceArea(slice: SliceRecord): number {
  return slice.bbox.width * slice.bbox.height;
}

function nextCopyName(name: string): string {
  return name.trim() ? `${name.trim()} copy` : "slice copy";
}

function isArrowKey(key: string): boolean {
  return key === "ArrowLeft" || key === "ArrowRight" || key === "ArrowUp" || key === "ArrowDown";
}

function arrowDelta(key: string, amount: number): Point {
  if (key === "ArrowLeft") return { x: -amount, y: 0 };
  if (key === "ArrowRight") return { x: amount, y: 0 };
  if (key === "ArrowUp") return { x: 0, y: -amount };
  return { x: 0, y: amount };
}

function nearestGuide(value: number, guides: number[]): number | null {
  let best: number | null = null;
  let bestDistance = boxSnapThreshold + 1;
  for (const guide of guides) {
    const distance = Math.abs(value - guide);
    if (distance <= boxSnapThreshold && distance < bestDistance) {
      best = guide;
      bestDistance = distance;
    }
  }
  return best;
}

function pageStatusLabel(page: WorkbenchPage, isActive: boolean, text: ReviewText): string {
  if (isActive) return text.inReview;
  if (page.slices.length) return text.completed;
  return text.skipped;
}

function pageStatusClass(page: WorkbenchPage, isActive: boolean): string {
  if (isActive) return "reviewing";
  if (page.slices.length) return "completed";
  return "skipped";
}

function aiProgressPercent(progress: AiProgress): number {
  return Math.round(Math.min(100, Math.max(0, (progress.completed + progress.failed) / Math.max(1, progress.total) * 100)));
}

function formatMessage(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (match, key) => {
    const value = values[key];
    return value === undefined ? match : String(value);
  });
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "unknown error";
}

function isTransformerTarget(node: Konva.Node): boolean {
  if (node.className === "Transformer") return true;
  const parent = node.getParent();
  return parent?.className === "Transformer";
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
        cutMode: slice.cutMode,
        bbox: slice.bbox,
        selected: true as const
      }))
    }))
  };
}

function getPageCutMode(page: WorkbenchPage | null, fallback: CutMode): CutMode | "mixed" {
  if (!page || !page.slices.length) return fallback;
  const first = page.slices[0].cutMode;
  return page.slices.every((slice) => slice.cutMode === first) ? first : "mixed";
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

function withClientRevision(path: string, revision: number): string {
  if (!revision) return path;
  return `${path}${path.includes("?") ? "&" : "?"}r=${revision}`;
}
