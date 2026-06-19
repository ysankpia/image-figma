"use client";

import { useEffect, useState } from "react";
import {
  defaultWorkbenchPreferences,
  readWorkbenchPreferences,
  writeWorkbenchPreferences,
  type StageFooterItem,
  type WorkbenchPreferences
} from "@/shared/workbench-preferences";
import type { CutMode } from "@/shared/types";

const cutModeOptions: Array<{ value: CutMode; label: string; description: string }> = [
  { value: "rect", label: "矩形", description: "按框完整裁出，最稳定，适合大多数 UI 资产。" },
  { value: "subject", label: "抠主体", description: "保留主体透明背景，适合图标和独立物体。" },
  { value: "card", label: "保内图", description: "保留框内图片内容，适合截图中的图片块。" }
];

const footerOptions: Array<{ value: StageFooterItem; label: string }> = [
  { value: "size", label: "页面尺寸" },
  { value: "zoom", label: "缩放比例" },
  { value: "status", label: "保存和任务状态" }
];

export function WorkbenchPreferencesForm() {
  const [preferences, setPreferences] = useState<WorkbenchPreferences>(defaultWorkbenchPreferences);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    setPreferences(readWorkbenchPreferences(window.localStorage));
    setLoaded(true);
  }, []);

  function updatePreferences(nextPreferences: WorkbenchPreferences) {
    setPreferences(nextPreferences);
    writeWorkbenchPreferences(window.localStorage, nextPreferences);
  }

  function updateCutMode(defaultCutMode: CutMode) {
    updatePreferences({ ...preferences, defaultCutMode });
  }

  function updateBoolean(key: "inspectorCollapsed" | "assetListCollapsed", value: boolean) {
    updatePreferences({ ...preferences, [key]: value });
  }

  function toggleFooterItem(item: StageFooterItem, enabled: boolean) {
    const nextItems = enabled
      ? [...new Set([...preferences.stageFooterItems, item])]
      : preferences.stageFooterItems.filter((current) => current !== item);
    updatePreferences({ ...preferences, stageFooterItems: nextItems });
  }

  function resetPreferences() {
    updatePreferences(defaultWorkbenchPreferences);
  }

  return (
    <div className="preferenceForm" aria-busy={!loaded}>
      <div className="preferenceBlock">
        <div>
          <h3>默认裁切模式</h3>
          <p>新建资产和进入工作台时的页面级默认模式。</p>
        </div>
        <div className="preferenceSegmented" role="radiogroup" aria-label="默认裁切模式">
          {cutModeOptions.map((option) => (
            <button
              key={option.value}
              type="button"
              className={preferences.defaultCutMode === option.value ? "active" : ""}
              role="radio"
              aria-checked={preferences.defaultCutMode === option.value}
              title={option.description}
              onClick={() => updateCutMode(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <div className="preferenceBlock">
        <div>
          <h3>工作台默认布局</h3>
          <p>控制每次进入复核页时右侧区域的初始展开状态。</p>
        </div>
        <div className="preferenceChecks">
          <label>
            <input
              type="checkbox"
              checked={preferences.inspectorCollapsed}
              onChange={(event) => updateBoolean("inspectorCollapsed", event.target.checked)}
            />
            <span>默认折叠右侧检查器</span>
          </label>
          <label>
            <input
              type="checkbox"
              checked={preferences.assetListCollapsed}
              onChange={(event) => updateBoolean("assetListCollapsed", event.target.checked)}
            />
            <span>默认折叠资产列表</span>
          </label>
        </div>
      </div>

      <div className="preferenceBlock">
        <div>
          <h3>底部状态栏</h3>
          <p>只保留你真正会看的信息，减少画布周围的干扰。</p>
        </div>
        <div className="preferenceChecks">
          {footerOptions.map((option) => (
            <label key={option.value}>
              <input
                type="checkbox"
                checked={preferences.stageFooterItems.includes(option.value)}
                onChange={(event) => toggleFooterItem(option.value, event.target.checked)}
              />
              <span>{option.label}</span>
            </label>
          ))}
        </div>
      </div>

      <div className="inlineActionRow">
        <button type="button" onClick={resetPreferences}>恢复默认工作台设置</button>
        <span className="sectionMeta">{loaded ? "设置会保存在当前浏览器。" : "正在读取设置。"}</span>
      </div>
    </div>
  );
}
