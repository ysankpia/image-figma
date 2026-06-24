import { httpError } from "./errors";
import { readEvidenceCache } from "./ocr-cache";
import { getPageOriginalKey, getProjectDetail } from "./projects";
import { compileSlicesToDraft } from "./slice-compiler";
import { estimateCornerRadius, sampleBgColor } from "./style-sampler";
import { storage } from "./storage";
import { publicApiBaseUrl } from "./config";

export async function exportFigmaDsl(userId: string, projectId: string, pageId: string) {
  const detail = await getProjectDetail(userId, projectId);
  const page = detail.pages.find((p) => p.id === pageId);
  if (!page) throw httpError(404, "Page not found");
  if (page.slices.length === 0) throw httpError(409, "No slices on this page");

  const originalKey = await getPageOriginalKey(userId, projectId, pageId);
  const originalBuffer = storage.read(originalKey, "Original image not found");

  const cache = readEvidenceCache(userId, projectId, originalBuffer);
  const ocrLines = cache?.ocr?.lines ?? [];

  // Sample style for card (container) slices
  const cardStyles = new Map<string, { fill: string; radius: number }>();
  const cardSlices = page.slices.filter((s) => s.cutMode === "card");
  await Promise.all(
    cardSlices.map(async (slice) => {
      const [fill, radius] = await Promise.all([
        sampleBgColor(originalBuffer, slice.bbox),
        estimateCornerRadius(originalBuffer, slice.bbox),
      ]);
      cardStyles.set(slice.id, { fill, radius });
    })
  );

  const dsl = compileSlicesToDraft(page.slices, ocrLines, page, projectId, publicApiBaseUrl);

  // Inject sampled styles into frame nodes
  function applyCardStyles(node: (typeof dsl.root)): void {
    if (node.type === "frame" && node.id !== "root") {
      const s = cardStyles.get(node.id);
      if (s) {
        node.style = { ...node.style, fill: s.fill, radius: s.radius };
      }
    }
    node.children?.forEach(applyCardStyles);
  }
  applyCardStyles(dsl.root);

  return new Response(JSON.stringify(dsl), {
    headers: { "Content-Type": "application/json" },
  });
}
