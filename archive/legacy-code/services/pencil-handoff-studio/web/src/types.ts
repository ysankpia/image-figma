export type BBox = { x: number; y: number; width: number; height: number };

export type Candidate = {
  id: string;
  pageId: string;
  kind: 'image' | 'icon' | 'text' | 'shape' | 'line' | 'ignore';
  bbox: BBox;
  confidence: number;
  sources: string[];
  reason: string;
};

export type PageDoc = {
  pageId: string;
  sourceImage: string;
  width: number;
  height: number;
  candidates?: Candidate[];
};

export type CandidatesDoc = {
  schema: string;
  projectId: string;
  projectName: string;
  pages: PageDoc[];
};

export type ManualSlice = {
  id: string;
  pageId: string;
  name: string;
  displayName: string;
  kind: 'image' | 'icon' | 'basic';
  bbox: BBox;
  selected: boolean;
  source: string;
  candidateIds: string[];
  tags: string[];
};

export type ManualPage = {
  pageId: string;
  sourceImage: string;
  width: number;
  height: number;
  slices: ManualSlice[];
};

export type ManualDoc = {
  schema: 'pencil.manual_slices.v1';
  projectName: string;
  pages: ManualPage[];
};

export type ReviewState = {
  schema: 'pencil_handoff.review_state.v1';
  projectId: string;
  activePageId: string | null;
  filters: {
    showHidden?: boolean;
    showCandidates?: boolean;
    showBasic?: boolean;
    colors?: Record<string, string>;
  };
  viewport: { x: number; y: number; scale: number };
  pages: Array<{
    pageId: string;
    hiddenCandidateIds: string[];
    rejectedCandidateIds: string[];
    lastFilter: string | null;
  }>;
  lastSavedAt: string;
};

export type ProjectSummary = {
  projectId: string;
  projectName: string;
  pageCount: number;
  candidateCount: number;
  selectedSliceCount: number;
  warnings?: string[];
  exported?: boolean;
  reviewUrl?: string;
  projectZipUrl?: string | null;
  assetsZipUrl?: string | null;
};

export type ToolMode = 'select' | 'draw' | 'pan';
export type HandleName = 'nw' | 'n' | 'ne' | 'e' | 'se' | 's' | 'sw' | 'w';
