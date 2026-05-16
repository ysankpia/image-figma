import type { DesignDSL } from "@image-figma/dsl-schema";
import { createFigmaAdapter, renderDesign } from "@image-figma/image-to-figma-renderer";
import mobileHome from "../../packages/dsl-schema/examples/mobile-home.dsl.json";

async function main(): Promise<void> {
  const result = await renderDesign(mobileHome as DesignDSL, {
    figma: createFigmaAdapter(figma as never),
    validate: true,
    createOriginalReference: true
  });

  if (result.success) {
    figma.notify(`Image-to-Figma smoke passed: ${result.renderedElementCount} elements`);
  } else {
    figma.notify(`Image-to-Figma smoke failed: ${result.errors[0]?.code ?? "UNKNOWN_ERROR"}`);
  }

  figma.closePlugin();
}

void main().catch((error) => {
  figma.notify(error instanceof Error ? error.message : "Image-to-Figma smoke failed");
  figma.closePlugin();
});
