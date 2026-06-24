export type PluginToMainMessage =
  | { type: "request-plugin-state" }
  | {
      type: "render-uploaded-png-draft";
      fileName: string;
      mimeType: "image/png";
      bytes: ArrayBuffer | Uint8Array | number[];
    }
  | { type: "render-sample" }
  | { type: "render-slice-studio-dsl"; dslUrl: string }
  | { type: "cancel" };

export type MainToPluginMessage =
  | { type: "plugin-state"; state: PluginState }
  | { type: "render-started"; source: "draft" | "sample" }
  | {
      type: "render-succeeded";
      renderedElementCount: number;
      warningCount: number;
      warnings: PluginRenderMessage[];
      diagnostics?: PluginDraftDiagnostics;
    }
  | {
      type: "render-failed";
      message: string;
      errors: PluginRenderMessage[];
      warnings: PluginRenderMessage[];
    }
  | { type: "status"; message: string; tone: "normal" | "success" | "error" };

export type PluginState = {
  pluginName: "Image-to-Figma Design";
  mode: "upload";
  rendererReady: boolean;
  apiBaseUrl: string;
};

export type PluginDraftDiagnostics = {
  ocrProvider?: string;
  ocrTextCount?: number;
  ocrCacheHit?: boolean;
  textLayerCount?: number;
  rasterLayerCount?: number;
  shapeLayerCount?: number;
  missingAssetCount?: number;
};

export type PluginRenderMessage = {
  code: string;
  message: string;
  elementId?: string;
};
