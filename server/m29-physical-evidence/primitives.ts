import { classifyComponent } from "./classify";
import { measureComponent, measureSurface } from "./measure";
import type { DecodedRgbaImage, M29OcrBlock, M29Primitive, PixelComponent, Rgb } from "./types";

export function buildPrimitives(input: {
  image: DecodedRgbaImage;
  background: Rgb;
  components: PixelComponent[];
  ocrBlocks?: M29OcrBlock[];
}): M29Primitive[] {
  const primitives: M29Primitive[] = [];
  for (const [index, block] of (input.ocrBlocks || []).entries()) {
    primitives.push({
      id: `prim_text_${String(index + 1).padStart(4, "0")}`,
      primitiveType: "text_region",
      bbox: { ...block.bbox },
      source: {
        kind: "ocr" as const,
        ocrBlockId: block.id,
        text: block.text
      },
      measurements: {
        ...measureSurface(input.image, block.bbox, input.background),
        textMaskArea: block.bbox.width * block.bbox.height
      },
      compileHints: {
        canBeLayerBackground: false,
        canContainForeground: false,
        canBeImage: false,
        canBeIcon: false,
        hasStableRectGeometry: false,
        confidence: block.confidence === undefined ? 0.8 : Math.max(0, Math.min(1, block.confidence)),
        reasons: ["ocr_text_region", "text_mask_source"]
      }
    });
  }
  const imageArea = input.image.width * input.image.height;
  const componentPrimitives = input.components.map((component, index) => {
    const measurements = measureComponent(input.image, component, input.background);
    const classification = classifyComponent(component, measurements, imageArea);
    return {
      id: `prim_${String(index + 1).padStart(4, "0")}`,
      primitiveType: classification.primitiveType,
      bbox: { ...component.bbox },
      source: { kind: "pixel" as const },
      measurements,
      compileHints: classification.compileHints
    };
  });
  primitives.push(...componentPrimitives);
  return primitives.sort((a, b) => a.bbox.y - b.bbox.y || a.bbox.x - b.bbox.x || a.id.localeCompare(b.id));
}
