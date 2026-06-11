import { classifyComponent } from "./classify";
import { measureComponent } from "./measure";
import type { DecodedRgbaImage, M29Primitive, PixelComponent, Rgb } from "./types";

export function buildPrimitives(input: {
  image: DecodedRgbaImage;
  background: Rgb;
  components: PixelComponent[];
}): M29Primitive[] {
  const imageArea = input.image.width * input.image.height;
  const primitives = input.components.map((component, index) => {
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
  return primitives.sort((a, b) => a.bbox.y - b.bbox.y || a.bbox.x - b.bbox.x || a.id.localeCompare(b.id));
}
