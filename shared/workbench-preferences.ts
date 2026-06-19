import type { CutMode } from "./types";

export type StageFooterItem = "size" | "zoom" | "status";

export type WorkbenchPreferences = {
  defaultCutMode: CutMode;
  inspectorCollapsed: boolean;
  assetListCollapsed: boolean;
  stageFooterItems: StageFooterItem[];
};

export const workbenchPreferencesStorageKey = "sliceStudio.workbenchPreferences.v1";

export const defaultWorkbenchPreferences: WorkbenchPreferences = {
  defaultCutMode: "rect",
  inspectorCollapsed: false,
  assetListCollapsed: false,
  stageFooterItems: ["size", "zoom", "status"]
};

const cutModes: CutMode[] = ["rect", "subject", "card"];
const stageFooterItems: StageFooterItem[] = ["size", "zoom", "status"];

export function parseWorkbenchPreferences(value: unknown): WorkbenchPreferences {
  const source = isRecord(value) ? value : {};
  const defaultCutMode = cutModes.includes(source.defaultCutMode as CutMode)
    ? source.defaultCutMode as CutMode
    : defaultWorkbenchPreferences.defaultCutMode;
  const footerItems = Array.isArray(source.stageFooterItems)
    ? source.stageFooterItems.filter((item): item is StageFooterItem => stageFooterItems.includes(item as StageFooterItem))
    : defaultWorkbenchPreferences.stageFooterItems;

  return {
    defaultCutMode,
    inspectorCollapsed: typeof source.inspectorCollapsed === "boolean" ? source.inspectorCollapsed : defaultWorkbenchPreferences.inspectorCollapsed,
    assetListCollapsed: typeof source.assetListCollapsed === "boolean" ? source.assetListCollapsed : defaultWorkbenchPreferences.assetListCollapsed,
    stageFooterItems: [...new Set(footerItems)]
  };
}

export function readWorkbenchPreferences(storage: Pick<Storage, "getItem">): WorkbenchPreferences {
  try {
    const raw = storage.getItem(workbenchPreferencesStorageKey);
    return parseWorkbenchPreferences(raw ? JSON.parse(raw) : null);
  } catch {
    return defaultWorkbenchPreferences;
  }
}

export function writeWorkbenchPreferences(storage: Pick<Storage, "setItem">, preferences: WorkbenchPreferences): void {
  storage.setItem(workbenchPreferencesStorageKey, JSON.stringify(parseWorkbenchPreferences(preferences)));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
