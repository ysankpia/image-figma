export type SliceKind = "image";
export type CutMode = "rect" | "subject" | "card";

export type BBox = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export type ProjectSummary = {
  id: string;
  name: string;
  createdAt: string;
  updatedAt: string;
  pageCount: number;
  sliceCount: number;
};

export type ProjectListItem = ProjectSummary & {
  firstPage: PageRecord | null;
};

export type PageRecord = {
  id: string;
  projectId: string;
  pageIndex: number;
  originalName: string;
  displayName: string;
  width: number;
  height: number;
  sourceUrl: string;
  thumbnailUrl: string;
};

export type SliceRecord = {
  id: string;
  projectId: string;
  pageId: string;
  sliceIndex: number;
  name: string;
  kind: SliceKind;
  cutMode: CutMode;
  bbox: BBox;
  selected: true;
};

export type ProjectDetail = {
  project: ProjectSummary;
  pages: Array<PageRecord & { slices: SliceRecord[] }>;
};

export type SaveSlicesRequest = {
  activePageId?: string | null;
  pages: Array<{
    pageId: string;
    slices: Array<{
      id: string;
      name: string;
      kind: SliceKind;
      cutMode?: CutMode;
      bbox: BBox;
      selected: true;
    }>;
  }>;
};

export type AiSliceBox = {
  bbox: BBox;
  name?: string;
  confidence?: number;
  reason?: string;
  sourceTileId: string;
};

export type AiSliceBoxesResponse = {
  ok: true;
  pageId: string;
  boxes: AiSliceBox[];
  diagnostics: {
    tileCount: number;
    rawBoxCount: number;
    acceptedBoxCount: number;
    rejectedBoxCount: number;
  };
};

export type AiSliceSettingsResponse = {
  ok: true;
  provider: "openai_responses" | "yolo_local" | "disabled";
  batchConcurrency: number;
  yoloClasses?: string[];
};

export type ExportJobKind = "assets" | "project" | "page_project";
export type ExportJobStatus = "queued" | "running" | "succeeded" | "failed" | "canceled";

export type ExportJobRecord = {
  id: string;
  projectId: string;
  kind: ExportJobKind;
  pageId?: string;
  status: ExportJobStatus;
  message: string;
  assetCount?: number;
  pageCount?: number;
  url?: string;
  cached?: boolean;
  error?: string;
  createdAt: string;
  updatedAt: string;
  startedAt?: string;
  finishedAt?: string;
};

export type CreateExportJobRequest = {
  kind: ExportJobKind;
  pageId?: string;
};

export type ExportJobResponse = {
  ok: true;
  job: ExportJobRecord;
};

export type ExportJobsResponse = {
  ok: true;
  jobs: ExportJobRecord[];
};

export type ExportManifest = {
  schema: "manual_ui_slices.v1";
  exportedAt: string;
  project: ProjectSummary;
  pages: Array<{
    pageId: string;
    originalName: string;
    displayName: string;
    pageDirectory: string;
    original: string;
    width: number;
    height: number;
    slices: Array<{
      id: string;
      name: string;
      kind: SliceKind;
      cutMode: CutMode;
      filename: string;
      placement: BBox;
      selected: true;
    }>;
  }>;
};

export type ToolMode = "select" | "draw" | "pan";

export type SaveState = "idle" | "saving" | "saved" | "error";
