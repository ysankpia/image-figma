import { describe, expect, it } from "vitest";
import {
  defaultWorkbenchPreferences,
  parseWorkbenchPreferences,
  readWorkbenchPreferences,
  workbenchPreferencesStorageKey,
  writeWorkbenchPreferences
} from "../shared/workbench-preferences";

describe("workbench preferences", () => {
  it("keeps valid preferences and allows hiding every stage footer item", () => {
    const preferences = parseWorkbenchPreferences({
      defaultCutMode: "card",
      inspectorCollapsed: true,
      assetListCollapsed: true,
      stageFooterItems: []
    });

    expect(preferences).toEqual({
      defaultCutMode: "card",
      inspectorCollapsed: true,
      assetListCollapsed: true,
      stageFooterItems: []
    });
  });

  it("falls back when stored preferences are malformed", () => {
    const preferences = parseWorkbenchPreferences({
      defaultCutMode: "bad",
      inspectorCollapsed: "yes",
      assetListCollapsed: null,
      stageFooterItems: ["zoom", "bad", "zoom"]
    });

    expect(preferences).toEqual({
      ...defaultWorkbenchPreferences,
      stageFooterItems: ["zoom"]
    });
  });

  it("reads and writes local storage compatible values", () => {
    const store = new Map<string, string>();
    const storage = {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => {
        store.set(key, value);
      }
    };

    writeWorkbenchPreferences(storage, {
      defaultCutMode: "subject",
      inspectorCollapsed: false,
      assetListCollapsed: true,
      stageFooterItems: ["status"]
    });

    expect(store.has(workbenchPreferencesStorageKey)).toBe(true);
    expect(readWorkbenchPreferences(storage)).toEqual({
      defaultCutMode: "subject",
      inspectorCollapsed: false,
      assetListCollapsed: true,
      stageFooterItems: ["status"]
    });
  });
});
