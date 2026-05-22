export type PluginToMainMessage =
  | { type: "request-plugin-state" }
  | {
      type: "render-uploaded-png";
      fileName: string;
      mimeType: "image/png";
      bytes: ArrayBuffer | Uint8Array | number[];
    }
  | {
      type: "render-uploaded-png-compare";
      fileName: string;
      mimeType: "image/png";
      bytes: ArrayBuffer | Uint8Array | number[];
    }
  | { type: "render-sample" }
  | { type: "cancel" };

export type MainToPluginMessage =
  | { type: "plugin-state"; state: PluginState }
  | { type: "render-started"; source: "upload" | "upload_compare" | "sample" }
  | {
      type: "render-succeeded";
      renderedElementCount: number;
      warningCount: number;
      warnings: PluginRenderMessage[];
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

export type PluginRenderMessage = {
  code: string;
  message: string;
  elementId?: string;
};
