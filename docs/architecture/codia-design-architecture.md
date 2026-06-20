# Codia Design — Architecture Specification

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CODIA DESIGN PIPELINE                           │
│                                                                         │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │ 1..N UI   │───▶│  Locate       │───▶│  OCR Text     │                  │
│  │ Screenshot│    │  Anything     │    │  Detection    │                  │
│  │  (PNG)    │    │ (ggml C++,    │    │ (Paddle/Tess) │                  │
│  │           │    │  3B, CPU/GPU) │    │               │                  │
│  └──────────┘    └──────┬───────┘    └──────┬───────┘                  │
│                         │                   │                           │
│                         ▼                   ▼                           │
│                    ┌────────────────────────────┐                       │
│                    │     Element Fusion          │                       │
│                    │  merge AI bboxes + OCR text  │                       │
│                    └────────────┬───────────────┘                       │
│                                 │                                       │
│                    ┌────────────▼───────────────┐                       │
│                    │    Style Extraction         │                       │
│                    │  colors, fonts, borders,     │                       │
│                    │  shadows, corner radii       │                       │
│                    └────────────┬───────────────┘                       │
│                                 │                                       │
│                    ┌────────────▼───────────────┐                       │
│                    │    Layout Analysis           │                       │
│                    │  Auto Layout tree,           │                       │
│                    │  spacing, padding, alignment │                       │
│                    └────────────┬───────────────┘                       │
│                                 │                                       │
│                    ┌────────────▼───────────────┐                       │
│                    │    Component Detection       │                       │
│                    │  repeated patterns →          │                       │
│                    │  component defs + instances   │                       │
│                    └────────────┬───────────────┘                       │
│                                 │                                       │
│                    ┌────────────▼───────────────┐                       │
│                    │    DSL Generation            │                       │
│                    │  DesignDSL v2.0 JSON          │                       │
│                    └────────────┬───────────────┘                       │
│                                 │                                       │
│                    ┌────────────▼───────────────┐                       │
│                    │    Figma Plugin              │                       │
│                    │  DSL → Figma nodes            │                       │
│                    │  (frame, text, rectangle,     │                       │
│                    │   auto-layout, components)    │                       │
│                    └──────────────────────────────┘                       │
└─────────────────────────────────────────────────────────────────────────┘
```

## 2. Pipeline Stages — Detailed Specification

### Stage 0: Image Ingest

```
INPUT:  PNG file path (or Buffer)
OUTPUT: ImageMeta + RawPixels

ImageMeta {
  path: string
  width: number   // px
  height: number  // px
  format: "png" | "jpg"
  colorSpace: "rgba"
}

RawPixels {
  data: Uint8Array   // RGBA, width * height * 4 bytes
  width: number
  height: number
}
```

**Algorithm**: Load PNG, decode to raw RGBA via sharp/libvips. No scaling — work at native resolution. If image > 2500px in any dimension, scale down preserving aspect ratio to max 2500px (LocateAnything model's native resolution limit).

**Edge cases**: Non-RGBA PNGs → convert to RGBA. Corrupt images → reject with clear error. Transparent images → fill transparency with white (#FFFFFF).

**Test**: Given a 1920×1080 screenshot, output has `width=1920, height=1080, data.length=8294400`.

---

### Stage 1: LocateAnything UI Element Detection

```
INPUT:  PNG file path + category list
OUTPUT: DetectionResult

DetectionResult {
  elements: DetectedElement[]
  model: string           // "LocateAnything-3B" 
  modelSize: string        // "q8_0" | "f16" | "f32"
  backend: "ggml-cpu" | "ggml-cuda" | "ggml-metal"
  inferenceTimeMs: number
  detectedCount: number
}

DetectedElement {
  id: string              // "elem_0001"
  type: ElementType       // see below
  bbox: BBox              // { x, y, width, height } in image px
                          // Model outputs normalized coords [0,1000],
                          // we convert to pixel coords
  confidence: number      // estimated from model behavior (not natively provided)
  label: string           // the label/category that was matched, e.g. "button"
}

ElementType = 
  | "button"       // clickable button
  | "input"        // text input field
  | "text"         // standalone text label
  | "image"        // image/illustration/photo
  | "icon"         // small icon
  | "card"         // card container
  | "navbar"       // top/bottom navigation bar
  | "tabbar"       // tab bar
  | "list"         // list/table
  | "modal"        // modal/dialog/popover
  | "divider"      // horizontal/vertical divider
  | "container"    // generic container
  | "other"        // unrecognized
```

**Engine**: [`locate-anything.cpp`](https://github.com/mudler/locate-anything.cpp) — C++/ggml port of NVIDIA LocateAnything-3B. Runs on CPU (no GPU required) via ggml, or GPU via CUDA/Metal backends.

**Model**: [`mudler/locate-anything.cpp-gguf`](https://huggingface.co/mudler/locate-anything.cpp-gguf) — pre-quantized GGUF files. Recommended: `q8_0` (~6.3 GB, box-identical to f32, ~5s per image on modern CPU).

**Algorithm — Multi-pass detection**:

LocateAnything is an open-vocabulary detector — it finds objects matching a text description. We run it in multiple passes, each targeting a different UI element type. The prompts are based on the model's supported task templates.

```
Pass 1: Container elements
  Prompt: "Locate all the instances that matches the following description: 
           navigation bar</c>tab bar</c>card container</c>list container</c>
           modal dialog</c>sidebar</c>header</c>footer."
  → Parsed: DetectedElement[] for structural containers

Pass 2: Interactive elements
  Prompt: "Locate all the instances that matches the following description: 
           button</c>text input field</c>search bar</c>dropdown menu</c>
           toggle switch</c>checkbox</c>radio button</c>slider."
  → Parsed: DetectedElement[] for interactive controls

Pass 3: Content elements  
  Prompt: "Locate all the instances that matches the following description: 
           image</c>icon</c>avatar</c>banner</c>illustration</c>chart."
  → Parsed: DetectedElement[] for visual content

Pass 4: Text elements (if OCR is unavailable)
  Prompt: "Detect all the text in box format."
  → Parsed: DetectedElement[] for text regions (if OCR not used)
```

**Post-processing**:
1. Parse model output: extract `<box><x1><y1><x2><y2></box>` tokens from response text
2. Convert normalized coordinates [0, 1000] to pixel coordinates using image dimensions
3. Deduplicate across passes: if two passes detect the same object (bbox IoU > 0.8), keep the higher-confidence pass result
4. Assign element type based on which pass detected it
5. Estimate confidence: heuristic based on bbox size consistency and label match

**Performance**:

| Mode | Hardware | Time (per pass) | Memory |
|------|----------|----------------|--------|
| q8_0, ggml-cpu | Ryzen 9 9950X (16 thr) | ~5s | ~6.3 GB |
| q8_0, ggml-cuda | NVIDIA GB10 | ~2s | ~6.3 GB VRAM |
| f16, ggml-cuda | NVIDIA GB10 | ~3s | ~9.2 GB VRAM |

For 4 detection passes on CPU: ~20s total. On GPU with batching: ~8s total.

**Edge cases**: 
- Model returns 0 detections → use heuristic fallback (YOLO or edge detection + connected components)
- Model returns overlapping boxes → keep highest match, split remaining area
- Very large images (> 2.5K resolution) → the model supports native resolution up to 2.5K; for larger, resize and scale coordinates back
- Model hallucinates boxes outside image bounds → clamp to [0, width] × [0, height]

**Test**: Given a login screen, Pass 1 detects navbar + card, Pass 2 detects 2 buttons + 2 inputs, Pass 3 detects 1 icon. Total: 6 elements covering >80% of UI.

---

### Stage 2: OCR Text Detection

```
INPUT:  RawPixels (or PNG Buffer)
OUTPUT: OcrResult

OcrResult {
  lines: OcrLine[]
  provider: "baidu_ppocrv5" | "tesseract"
  language: string       // "zh+en" or "eng"
}

OcrLine {
  text: string           // detected text content
  bbox: BBox             // tight bounding box around text glyphs
  confidence: number     // 0..1 OCR confidence
  wordCount: number
}
```

**Algorithm**: 
- Call Baidu PaddleOCR (remote API, submit job → poll → download JSONL) OR Tesseract (local subprocess `tesseract input.png stdout -l chi_sim+eng --psm 6 tsv`).
- Parse results into `OcrLine[]`.
- Filter: confidence >= 0.70, text not empty, bbox not degenerate.
- Sort by y-position then x-position (reading order).

**Edge cases**: OCR token not configured → skip OCR, return empty lines. Tesseract not installed → skip. Vertical text → handled by OCR engine. Rotated text → Tesseract --psm 6 handles some rotation.

**Test**: Given a screenshot with "登录" and "注册" text, output has 2 lines with text "登录" and "注册" and reasonable bboxes.

---

### Stage 3: Element Fusion

```
INPUT:  DetectionResult + OcrResult
OUTPUT: UnifiedElement[]

UnifiedElement {
  id: string
  type: ElementType
  bbox: BBox
  children: UnifiedElement[]   // nested elements
  parentId: string | null

  // Text (if this element contains text)
  text?: {
    content: string            // from OCR, matched to this element
    ocrBBox: BBox             // OCR's tight bbox
    physicalBBox?: BBox       // refined bbox from m29/physical evidence
  }

  // Visual properties (to be filled by Stage 4)
  visual?: ElementVisual

  // Layout (to be filled by Stage 5)
  layout?: LayoutHint
}

ElementVisual {
  backgroundColor: string     // "#RRGGBB" or "transparent"
  textColor: string           // "#RRGGBB"
  fontSize: number            // px
  fontFamily: string           // "PingFang SC", "Inter", etc.
  fontWeight: string           // "400", "500", "600", "700"
  cornerRadius: number         // px
  border?: {
    color: string
    width: number              // px
    style: "solid" | "dashed"
  }
  shadow?: {
    color: string
    offsetX: number
    offsetY: number
    blur: number
    spread: number
  }
  opacity: number              // 0..1
}

LayoutHint {
  direction: "horizontal" | "vertical" | "none"
  gap: number                  // px between children
  padding: { top: number; right: number; bottom: number; left: number }
  mainAxisAlignment: "start" | "center" | "end" | "space-between"
  crossAxisAlignment: "start" | "center" | "end" | "stretch"
  childrenBBoxes: BBox[]       // bbox of each direct child relative to parent
}
```

**Algorithm — Fusion**:
1. For each AI-detected element, find the best-matching OCR line: OCR bbox ∩ element bbox, highest overlap ratio wins.
2. If an OCR line has no matching AI element, create a new "text" element for it.
3. If an AI element has no matching OCR line, keep it as-is.
4. Sort elements by y-position, then x-position.
5. Resolve parent-child relationships: element A is parent of element B if B's bbox is fully inside A's bbox (with 2px margin) and A's type is a container type (card, navbar, list, modal, container).
6. Flatten deeply nested trees (max depth 3: page → container → leaf).

**Edge cases**: Overlapping detections → keep the higher-confidence one, split area. OCR text that spans multiple AI elements → assign to the element with highest overlap. Missing parent → make it a direct child of the page root.

**Test**: Given AI detection of a card containing image + title + button, and OCR detecting the title text, the output has a card element with image+text+button children, and the text child has `text.content` from OCR.

---

### Stage 4: Style Extraction

```
INPUT:  UnifiedElement[] + RawPixels
OUTPUT: UnifiedElement[] (with visual fields filled)
```

**Algorithm — Per element type**:

**For "text" elements** (with text content):
1. Extract the text bbox region from RawPixels.
2. Estimate text color: sample pixels inside the OCR bbox, find the dominant non-background color (pixels that differ from local background by >30 color distance).
3. Estimate background color: sample pixels just outside the bbox (ring of 4-8px), take median.
4. Estimate font size: measure text height from bbox, use heuristic: `fontSize ≈ bbox.height * 0.75` for CJK, `* 0.85` for Latin.
5. Font family: "PingFang SC" for CJK text, "Inter" for Latin-only text (hardcoded defaults).
6. Font weight: sample the text pixels' darkness relative to background. If (textColor - backgroundColor) contrast > 100 luminance units → weight 700 (bold), else 400 (regular).
7. Call external text style service for high-precision measurement (optional, see below).

**For "button", "input", "card", "container" elements**:
1. Extract the element's bbox region.
2. Estimate background color: sample interior pixels (excluding text areas), find the dominant color.
3. Estimate corner radius: scan the 4 corners of the bbox, find where the background color transitions to different color — the distance from the corner to the transition is the radius. Fallback: 8px for buttons, 12px for cards, 4px for inputs.
4. Detect border: scan the perimeter pixels. If a consistent color band of 1-3px exists outside the background → border exists.
5. Detect shadow: scan pixels just outside the bbox edges (bottom+right sides). If there's a dark gradient → shadow exists. Estimate offset and blur from gradient profile.

**For "image", "icon" elements**:
1. The element's visual content IS the image/icon. No style extraction needed.
2. For icons: check if the element area is mostly transparent (alpha < 10 for > 50% of pixels). If transparent, the element is an icon with transparent background. The visible pixels form the icon shape. Apply vectorization (Stage 4b).

**Text Style Service (optional precision step)**:
- Call an external service (e.g., PSD-like text style measurement) that analyzes the text region at pixel level to measure exact font size, weight, line height, and text alignment.
- The service takes (imageBuffer, [{ text, bbox }]) and returns [{ fontSize, fontWeight, fontFamily, color, lineHeight, textAlign }].
- If service is unavailable, use heuristics above.

**Edge cases**: Elements with gradients → pick the average/most common color. Elements with background images → mark visual as "image fill" rather than solid color. Semi-transparent elements → measure the composited color against the underlying background.

**Test**: Given a blue button (#1677FF) with white text "提交" at 16px, output has `visual.backgroundColor = "#1677FF"`, `textColor = "#FFFFFF"`, `fontSize ≈ 16`, `cornerRadius ≈ 8`.

---

### Stage 4b: Icon Vectorization (optional enhancement)

```
INPUT:  Icon element (UnifiedElement with type "icon") + RawPixels
OUTPUT: SVG path data string
```

**Algorithm**:
1. Extract the icon's bbox from RawPixels.
2. Binarize: threshold alpha channel at 128. Pixels with alpha >= 128 → foreground, < 128 → background.
3. If the icon has color (non-monochrome): keep it as a raster image (skip vectorization).
4. If monochrome: run edge detection (Canny or Sobel), then trace contours (marching squares or OpenCV findContours).
5. Simplify contours with Ramer-Douglas-Peucker algorithm (epsilon = 1.5px) to reduce vertex count.
6. Convert to SVG path data: `M x,y L x,y ... Z` for each closed contour.
7. Color: the foreground color of the icon.

**Alternative (simpler)**:
- Use `potrace` CLI tool: save icon region as PBM, run potrace, parse SVG output.

**Edge cases**: Multi-color icons → keep as raster. Very small icons (< 16px) → skip vectorization. Complex shapes → RDP simplification may lose detail; tune epsilon.

---

### Stage 5: Layout Analysis

```
INPUT:  UnifiedElement[] (with bbox + type + children)
OUTPUT: LayoutNode tree

LayoutNode {
  id: string
  type: ElementType
  bbox: BBox                    // absolute position
  visual: ElementVisual
  text?: { content, ... }
  layout: AutoLayoutConfig
  children: LayoutNode[]
  isComponent: boolean
  componentId?: string
}

AutoLayoutConfig {
  direction: "horizontal" | "vertical" | "none"
  gap: number                   // px
  padding: Padding
  mainAxisAlign: "start" | "center" | "end" | "space-between"
  crossAxisAlign: "start" | "center" | "end" | "stretch"
  layoutMode: "none"            // always "none" for Figma — use Auto Layout instead
  wraps: boolean                // wrap children to next row?
}
```

**Algorithm — Layout inference**:

For each container element (type in {card, navbar, tabbar, list, container, modal}):

1. **Get children**: elements whose `parentId` points to this container.

2. **Detect direction**:
   - If children are arranged L→R with similar Y centers → "horizontal"
   - If children are arranged T→B with similar X positions → "vertical"
   - If children form a grid (multiple rows AND columns) → "vertical" with `wraps: true`
   - Otherwise → "none" (absolute positioning)

   Pseudocode:
   ```
   xs = [child.bbox.x for child in children]
   ys = [child.bbox.y for child in children]
   if std(xs) > std(ys) * 2 → vertical
   if std(ys) > std(xs) * 2 → horizontal
   if std(xs) > width * 0.3 AND std(ys) > height * 0.3 → grid (vertical + wraps)
   else → none
   ```

3. **Detect gap** (spacing between adjacent children):
   - For horizontal: `gap = median([children[i+1].bbox.x - (children[i].bbox.x + children[i].bbox.width) for i in range(n-1)])`
   - For vertical: `gap = median([children[i+1].bbox.y - (children[i].bbox.y + children[i].bbox.height) for i in range(n-1)])`
   - Clamp gap to [0, 120] px.

4. **Detect padding**:
   - `padding.top = min([child.bbox.y for child in children]) - container.bbox.y`
   - `padding.left = min([child.bbox.x for child in children]) - container.bbox.x`
   - `padding.bottom = (container.bbox.y + container.bbox.height) - max([child.bbox.y + child.bbox.height for child in children])`
   - `padding.right = (container.bbox.x + container.bbox.width) - max([child.bbox.x + child.bbox.width for child in children])`
   - Clamp each to [0, 40] px.

5. **Detect alignment**:
   - For vertical containers: check if children have the same `x` (→ "start"), same `centerX` (→ "center"), same `right` (→ "end"), or if first and last are at edges (→ "space-between").
   - Same logic for horizontal containers with `y`/`centerY`/`bottom`.
   - `crossAxisAlignment`: if all children have same height in vertical → "stretch"? Actually, check if edges align.

6. **Recurse**: apply layout detection to each child that is itself a container.

**Edge cases**: Containers with a single child → direction=none, alignment=start. Empty containers → keep bbox but no Auto Layout. Mixed content (some text, some images) → analyze by type groups.

**Test**: Given a vertical card with title (top), image (middle), button (bottom), output has `direction: "vertical"`, reasonable gap and padding, `crossAxisAlignment: "stretch"` (children full width).

---

### Stage 6: Component Detection

```
INPUT:  LayoutNode tree
OUTPUT: LayoutNode tree (with component annotations)

ComponentDefinition {
  id: string              // "comp_0001"
  name: string            // human-readable: "Card", "NavItem", "InputField"
  signature: string       // structural hash for matching
  template: LayoutNode    // the component's internal structure
  instances: string[]     // IDs of nodes that are instances
  count: number           // how many times this pattern appears
}
```

**Algorithm**:

1. **Flatten and hash**: For each container node, compute a "structural signature":
   ```
   signature = join([
     container.type,
     join(sort([child.type for child in container.children])),
     container.layout.direction,
     round(container.bbox.width / container.bbox.height, 1)
   ], "|")
   ```
   Example: `"card|button,image,text|vertical|0.75"`

2. **Cluster by signature**: Group nodes with the same signature.

3. **Filter candidates**: Only consider clusters with count >= 3. Also filter by structural similarity:
   - Children must be the same types in the same order.
   - Width/height ratio must be within 10% tolerance.
   - Gap and padding within 15% tolerance.

4. **Refine with visual similarity**: Within each cluster, compare the visual properties of corresponding children:
   - Background colors within 30 color distance.
   - Font sizes within 2px.
   - Text content similarity (for placeholder text) — if texts are identical, it's a strong signal.

5. **Create component definitions**: For each validated cluster:
   - Create a `ComponentDefinition` with the first instance as template.
   - Mark all instances as `isComponent: true, componentId: compId`.
   - Name the component based on the most common text content or element types.

6. **Generate component property overrides**: For each instance, compute the differences from the template (different text content, different image source, different width/height).

**Edge cases**: Lists with many similar items → detect as a single component with N instances. Cards with different content → might be different components. Buttons with different text → same component, different text override.

**Test**: Given a list of 5 identical cards each with image + title + button, output has 1 component definition and 5 instances.

---

### Stage 7: DSL Generation

```
INPUT:  LayoutNode tree + ComponentDefinition[]
OUTPUT: DesignDSL (JSON file)
```

```typescript
// DesignDSL v2.0 — the Codia Design output format
interface DesignDSL {
  schema: "codia_design_dsl.v2"
  meta: {
    generatedAt: string       // ISO 8601
    sourceImage: {
      width: number
      height: number
      format: "png"
    }
    model: string              // AI model used for detection
    ocrProvider: string
    elementCount: number
    componentCount: number
    textCount: number
  }
  designTokens: {
    colors: ColorToken[]
    textStyles: TextStyleToken[]
    effects: EffectToken[]
  }
  components: ComponentDef[]
  page: DesignPage
  assets: DesignAsset[]
}

interface DesignPage {
  id: string                   // "page_root"
  name: string                 // "Page 1" or screenshot filename
  width: number
  height: number
  root: DesignNode             // the root frame
}

interface DesignNode {
  id: string
  name: string
  type: "frame" | "text" | "rectangle" | "vector" | "instance"
  
  // Position & size (for non-auto-layout children)
  x?: number
  y?: number
  width: number
  height: number
  
  // Auto Layout (for containers)
  autoLayout?: {
    direction: "horizontal" | "vertical"
    gap: number
    padding: { top: number; right: number; bottom: number; left: number }
    mainAxisAlign: string
    crossAxisAlign: string
  }
  
  // Visual
  fills: DesignFill[]
  strokes?: DesignStroke[]
  cornerRadius?: number
  opacity?: number
  effects?: DesignEffect[]
  
  // Text
  text?: string
  textStyle?: string           // reference to TextStyleToken
  textAlign?: "left" | "center" | "right"
  
  // Component
  componentId?: string
  componentOverrides?: Record<string, unknown>
  
  // Children
  children?: DesignNode[]
}

interface DesignFill {
  type: "solid" | "image"
  color?: string              // "#RRGGBB" or "rgba(r,g,b,a)"
  imageUrl?: string           // relative path to asset
  opacity?: number
}

interface DesignStroke {
  color: string
  weight: number
  align: "inside" | "outside" | "center"
}

interface DesignEffect {
  type: "drop-shadow" | "inner-shadow" | "blur"
  color: string
  offset?: { x: number; y: number }
  radius: number
  spread?: number
}

interface ColorToken {
  id: string
  name: string                // "Primary Blue", "Text/Primary", etc.
  value: string               // "#RRGGBB"
  usage: string[]             // element IDs using this color
}

interface TextStyleToken {
  id: string
  name: string                // "Heading", "Body", "Button"
  fontFamily: string
  fontSize: number
  fontWeight: string
  lineHeight: number
  color: string
  usage: string[]
}

interface ComponentDef {
  id: string
  name: string                // "Card", "NavItem"
  template: DesignNode
  instanceCount: number
}

interface DesignAsset {
  id: string
  name: string
  type: "image" | "icon"
  url: string                 // relative path
  width: number
  height: number
  format: "png" | "svg"
}
```

**Algorithm — DSL Generation**:

1. **Extract Design Tokens**: Scan all `UnifiedElement.visual` values. Group similar colors (distance < 15) into `ColorToken`s. Group similar text styles (same font+size+weight+color) into `TextStyleToken`s. Name tokens by usage: "Primary Blue" for the most common blue, "Text/Primary" for the most common text color. If a color appears on >= 3 elements, create a token.

2. **Build DesignNode tree**: Walk the `LayoutNode` tree depth-first.
   - Container → `type: "frame"` with `autoLayout` if direction != "none".
   - Text element → `type: "text"` with `text` and `textStyle` reference.
   - Button → `type: "frame"` with `cornerRadius` + `fills`, contains a `type: "text"` child.
   - Image/Icon → `type: "rectangle"` with `fills: [{ type: "image", imageUrl: "..." }]`.
   - Divider → `type: "rectangle"` with `height: 1` and background fill.
   - Instance → `type: "instance"` with `componentId`.

3. **Generate X/Y for non-auto-layout children**: If the parent container has `autoLayout`, children's positions are managed by the layout engine — DO NOT set x/y. If the parent does NOT have autoLayout (direction=none), set x/y relative to parent's position.

4. **Resolve asset references**: For each image/icon element, crop the region from the source image, save as PNG. For vectorized icons, save as SVG. Asset URLs are relative to the DSL file: `"assets/img_0001.png"`.

5. **Validate the DSL**: Check that all references resolve, all IDs are unique, Auto Layout containers have children with no x/y overrides (Figma constraint).

**Edge cases**: Very large DSL files (> 1000 nodes) → Figma Plugin may be slow; consider pagination. Empty containers → skip in output. Nested Auto Layout (Auto Layout inside Auto Layout) → Figma supports this, correctly model parent-child auto-layout relationships.

**Test**: Given 5 elements (1 card, 1 image, 1 text, 1 button, 1 icon), output DSL has `components: 0`, `designTokens.colors.length >= 3`, `page.root.children.length = 1` (the card), with proper Auto Layout.

---

### Stage 8: Figma Plugin Rendering

```
INPUT:  DesignDSL JSON
OUTPUT: Figma nodes on the current page
```

**Algorithm — Figma Plugin (`plugin/src/main.ts`)**:

```typescript
// Core rendering loop
function renderDesign(dsl: DesignDSL): void {
  const page = dsl.page;
  const rootFrame = figma.createFrame();
  rootFrame.name = page.name;
  rootFrame.resize(page.width, page.height);
  rootFrame.fills = [{ type: 'SOLID', color: { r: 1, g: 1, b: 1 } }];

  // Create design tokens as Figma styles
  const colorStyles = createColorStyles(dsl.designTokens.colors);
  const textStyles = createTextStyles(dsl.designTokens.textStyles);

  // First pass: create components
  const componentMap = createComponents(dsl.components, textStyles);

  // Second pass: render node tree
  for (const node of page.root.children ?? []) {
    const figmaNode = renderNode(node, { colorStyles, textStyles, componentMap });
    rootFrame.appendChild(figmaNode);
  }

  figma.currentPage.appendChild(rootFrame);
  figma.viewport.scrollAndZoomIntoView([rootFrame]);
}

function renderNode(
  node: DesignNode,
  ctx: RenderContext
): SceneNode {
  switch (node.type) {
    case 'frame': return renderFrame(node, ctx);
    case 'text': return renderText(node, ctx);
    case 'rectangle': return renderRect(node, ctx);
    case 'vector': return renderVector(node, ctx);
    case 'instance': return renderInstance(node, ctx);
  }
}

function renderFrame(node: DesignNode, ctx: RenderContext): FrameNode {
  const frame = figma.createFrame();
  frame.name = node.name;
  frame.resize(node.width, node.height);

  if (node.x !== undefined) frame.x = node.x;
  if (node.y !== undefined) frame.y = node.y;

  // Fills
  if (node.fills?.length) {
    frame.fills = node.fills.map(convertFill);
  }

  // Corner radius
  if (node.cornerRadius) {
    frame.cornerRadius = node.cornerRadius;
  }

  // Strokes
  if (node.strokes?.length) {
    frame.strokes = node.strokes.map(convertStroke);
  }

  // Effects (shadow)
  if (node.effects?.length) {
    frame.effects = node.effects.map(convertEffect);
  }

  // Auto Layout
  if (node.autoLayout) {
    frame.layoutMode = node.autoLayout.direction.toUpperCase() as 'HORIZONTAL' | 'VERTICAL';
    frame.itemSpacing = node.autoLayout.gap;
    frame.paddingTop = node.autoLayout.padding.top;
    frame.paddingRight = node.autoLayout.padding.right;
    frame.paddingBottom = node.autoLayout.padding.bottom;
    frame.paddingLeft = node.autoLayout.padding.left;
    frame.primaryAxisAlignItems = convertAlign(node.autoLayout.mainAxisAlign);
    frame.counterAxisAlignItems = convertAlign(node.autoLayout.crossAxisAlign);
  }

  // Children
  if (node.children) {
    for (const child of node.children) {
      frame.appendChild(renderNode(child, ctx));
    }
  }

  return frame;
}

function renderText(node: DesignNode, ctx: RenderContext): TextNode {
  const text = figma.createText();
  text.name = node.name;
  text.resize(node.width, node.height);

  // Use text style if available
  if (node.textStyle && ctx.textStyles[node.textStyle]) {
    text.textStyleId = ctx.textStyles[node.textStyle];
  } else {
    // Apply inline text properties from visual
    // (fallback when no style token)
    text.fontSize = node.visual?.fontSize ?? 14;
    text.fontName = {
      family: node.visual?.fontFamily ?? 'Inter',
      style: node.visual?.fontWeight === '700' ? 'Bold' : 'Regular'
    };
    if (node.visual?.textColor) {
      text.fills = [{ type: 'SOLID', color: hexToRgb(node.visual.textColor) }];
    }
  }

  if (node.text) {
    text.characters = node.text;
  }
  if (node.textAlign) {
    text.textAlignHorizontal = node.textAlign.toUpperCase() as TextAlignHorizontal;
  }

  return text;
}

function renderRect(node: DesignNode, ctx: RenderContext): RectangleNode {
  const rect = figma.createRectangle();
  rect.name = node.name;
  rect.resize(node.width, node.height);

  if (node.fills?.length) {
    rect.fills = node.fills.map(convertFill);
  }
  if (node.strokes?.length) {
    rect.strokes = node.strokes.map(convertStroke);
  }
  if (node.cornerRadius) {
    rect.cornerRadius = node.cornerRadius;
  }
  if (node.effects?.length) {
    rect.effects = node.effects.map(convertEffect);
  }

  return rect;
}

function renderInstance(node: DesignNode, ctx: RenderContext): InstanceNode {
  const component = ctx.componentMap[node.componentId!];
  const instance = component.createInstance();
  instance.name = node.name;

  if (node.componentOverrides) {
    for (const [key, value] of Object.entries(node.componentOverrides)) {
      // Override text content, fill color, etc.
    }
  }

  return instance;
}

// Component creation
function createComponents(defs: ComponentDef[], ctx: RenderContext): Record<string, ComponentNode> {
  const map: Record<string, ComponentNode> = {};
  for (const def of defs) {
    const component = figma.createComponent();
    component.name = def.name;
    component.resize(def.template.width, def.template.height);
    // Render template children into component...
    // Render the template's children as the component's content
    // This is the ONE place where the component's internal structure is defined
    // All instances will inherit this structure
    map[def.id] = component;
  }
  return map;
}
```

**Edge cases**: Font loading → call `figma.loadFontAsync({ family, style })` before creating text nodes. Asset loading → images must be available at the specified URL (embedded as base64 or served locally). Large DSL → render in batches with progress indicator.

**Test**: Given a minimal DSL with 1 frame + 1 text node, Plugin creates a visible frame with "Hello" text in Figma.

---

## 3. Technology Stack Rationale

| Component | Technology | Why |
|-----------|-----------|-----|
| **Core Engine** | Rust | Single binary, fast image processing, existing pixel ops code, no GC pauses |
| **UI Element Detection** | LocateAnything-3B (ggml C++) | Open-vocabulary, 3B params, CPU-friendly via ggml, zero API cost, supports GUI grounding natively |
| **Fast Pre-Detection** (optional) | YOLO (Ultralytics, Python) | Fast first pass for common UI types; LocateAnything handles rare/long-tail elements |
| **OCR** | Baidu PaddleOCR (remote) or Tesseract (local) | Proven in Slice Studio; Tesseract for offline mode |
| **Text BBox Refinement** | M29 physical evidence (TypeScript) | Tighter text bbox from pixel-level foreground detection; already in Slice Studio |
| **Text Style Measurement** | PSD-like text style service (Python FastAPI) | Font size, weight, color, alignment measurement; already in Slice Studio |
| **Image Processing** | sharp (libvips) via Rust bindings | Fastest PNG decode/encode; Rust FFI available |
| **Figma Plugin** | TypeScript (required by Figma) | Figma Plugin API is JavaScript/TypeScript only |
| **Plugin Build** | esbuild or tsup | Bundle TypeScript to single JS file for Figma |
| **Testing** | Rust: `cargo test`; TS: `vitest` | Standard tools |
| **CLI** | Rust binary with `clap` | Pipeline runnable as: `codia-design input.png -o output/` |

**Cost model**: Zero API cost. Everything runs locally. LocateAnything on CPU: ~20s for full detection (4 passes). On GPU: ~8s. No per-image charges.

## 4. Directory Structure

```
codia-design/
├── README.md
├── Cargo.toml                      # Workspace root
├── Cargo.lock
├── rust-toolchain.toml             # Pin Rust version
├── .gitignore
│
├── crates/
│   ├── core/                       # Shared types and utilities
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── types.rs            # All shared data types
│   │       └── bbox.rs             # BBox operations (intersect, union, etc.)
│   │
│   ├── ingest/                     # Stage 0
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs
│   │       └── image.rs            # Load PNG, decode to RGBA
│   │
│   ├── detect/                     # Stage 1
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── locate.rs           # LocateAnything ggml C++ integration (FFI bindings)
│   │       ├── passes.rs           # Multi-pass detection orchestration
│   │       ├── parser.rs           # Parse model output → DetectedElement[]
│   │       └── yolo.rs             # Optional: YOLO fast pre-detection fallback
│   │
│   ├── ocr/                        # Stage 2
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── tesseract.rs        # Local Tesseract runner
│   │       └── paddle.rs           # Baidu PaddleOCR client
│   │
│   ├── fusion/                     # Stage 3
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── merge.rs            # AI + OCR fusion
│   │       └── tree.rs             # Build parent-child tree
│   │
│   ├── style/                      # Stage 4
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── color.rs            # Color sampling and estimation
│   │       ├── text.rs             # Text style measurement
│   │       ├── border.rs           # Border detection
│   │       ├── shadow.rs           # Shadow detection
│   │       ├── radius.rs           # Corner radius detection
│   │       └── vector.rs           # Icon vectorization (potrace)
│   │
│   ├── layout/                     # Stage 5
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── direction.rs        # Auto Layout direction detection
│   │       ├── spacing.rs          # Gap and padding detection
│   │       └── alignment.rs        # Alignment detection
│   │
│   ├── component/                  # Stage 6
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── hash.rs             # Structural hashing
│   │       ├── cluster.rs          # Similarity clustering
│   │       └── match.rs            # Instance matching
│   │
│   ├── dsl/                        # Stage 7
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── generate.rs         # LayoutNode → DesignDSL
│   │       ├── tokens.rs           # Design token extraction
│   │       ├── assets.rs           # Asset cropping and saving
│   │       └── validate.rs         # DSL validation
│   │
│   ├── pixel/                      # Pixel operations (Rust native)
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── inpaint.rs          # Inpaint masked regions
│   │       ├── dilate.rs           # Binary dilation
│   │       ├── cutout.rs           # Flood-fill background removal
│   │       └── geometry.rs         # Rounded rect, intersection, etc.
│   │
│   └── cli/                        # CLI binary
│       ├── Cargo.toml
│       └── src/
│           ├── main.rs             # CLI entry: parse args, run pipeline
│           └── pipeline.rs         # Orchestrate all stages
│
├── plugin/                         # Figma Plugin
│   ├── manifest.json
│   ├── package.json
│   ├── tsconfig.json
│   ├── src/
│   │   ├── main.ts                 # Plugin entry point
│   │   ├── renderer.ts             # DSL → Figma nodes
│   │   ├── adapter.ts              # Figma API wrappers
│   │   ├── styles.ts               # Color/text style creation
│   │   ├── components.ts           # Component creation + instances
│   │   └── ui.ts                   # Plugin UI (file picker, progress)
│   └── ui.html                     # Plugin UI markup
│
├── tests/                          # Integration tests
│   ├── fixtures/
│   │   ├── sample-login.png        # Test screenshot: login form
│   │   ├── sample-cards.png        # Test screenshot: card list
│   │   └── expected/
│   │       ├── login-dsl.json      # Expected DSL output
│   │       └── cards-dsl.json
│   ├── integration.rs              # Rust integration tests
│   └── pipeline.rs                 # End-to-end pipeline tests
│
├── samples/                        # Example outputs
│   ├── login-screen/
│   │   ├── input.png
│   │   ├── output.dsl.json
│   │   ├── debug/                  # Per-stage debug outputs
│   │   │   ├── 01-elements.json    # Stage 1 output
│   │   │   ├── 02-ocr.json         # Stage 2 output
│   │   │   ├── 03-fused.json       # Stage 3 output
│   │   │   ├── 04-styled.json      # Stage 4 output
│   │   │   ├── 05-layout.json      # Stage 5 output
│   │   │   └── 06-components.json  # Stage 6 output
│   │   └── assets/                 # Cropped images + icons
│   └── ecommerce-app/
│       └── ...
│
└── docs/
    ├── architecture.md              # This document
    ├── dsl-schema.md               # DSL v2.0 full schema reference
    ├── plugin-guide.md             # How to install and use the Figma plugin
    └── contributing.md             # Development setup
```

## 5. Implementation Phases

### Phase 1: Core Pipeline (Weeks 1-3)

**Goal**: End-to-end flow from screenshot → DSL JSON. No Figma Plugin yet.

| Step | Crate | Deliverable | Test |
|------|-------|------------|------|
| 1.1 | `core` | All shared types (`DetectedElement`, `UnifiedElement`, `LayoutNode`, `DesignDSL`) | Compile |
| 1.2 | `ingest` | Load PNG → RawPixels | Load test image, verify dimensions |
| 1.3 | `detect` | Build & integrate `locate-anything.cpp`; multi-pass UI detection | Run detection on test screenshot, verify parsed boxes |
| 1.4 | `ocr` | Run Tesseract → OcrLine[] | Tesseract on text image, verify lines |
| 1.5 | `fusion` | Merge AI + OCR → UnifiedElement[], build tree | Merge test data, verify parent-child |
| 1.6 | `style` | Extract colors, text styles, borders, shadows | Style extraction on test element, verify hex + fontSize |
| 1.7 | `layout` | Detect Auto Layout direction, gap, padding, alignment | Layout on test container, verify direction + gap |
| 1.8 | `dsl` | LayoutNode → DesignDSL JSON, crop assets, validate | Full pipeline, verify DSL JSON structure |
| 1.9 | `cli` | Wire everything together, `cargo run -- input.png -o out/` | E2E: screenshot in, DSL out |

### Phase 2: Figma Plugin (Weeks 4-5)

**Goal**: Load DSL in Figma, render editable design.

| Step | Deliverable | Test |
|------|------------|------|
| 2.1 | Plugin scaffold: manifest.json, build config | Plugin loads in Figma dev mode |
| 2.2 | DSL loader: file picker, parse JSON | Load DSL file, log to console |
| 2.3 | Frame renderer: createFrame, fills, cornerRadius | Render a card frame |
| 2.4 | Text renderer: createText, font loading, style | Render text with correct font + color |
| 2.5 | Auto Layout: layoutMode, spacing, padding | Render container with auto-layout and children |
| 2.6 | Components: createComponent, createInstance | Render repeated cards as instances |
| 2.7 | Full integration: load DSL, render everything | E2E: DSL in, Figma design out |

### Phase 3: Quality & Polish (Weeks 6-8)

| Step | Deliverable |
|------|------------|
| 3.1 | Icon vectorization (potrace integration) |
| 3.2 | Shadow detection refinement |
| 3.3 | Gradient detection (linear gradients) |
| 3.4 | Text style service integration for precise font measurement |
| 3.5 | Multi-page support (process N screenshots → N pages in Figma) |
| 3.6 | YOLO + LocateAnything hybrid: YOLO for fast common-element pre-pass, LocateAnything for rare/long-tail elements (faster, cheaper, offline) |
| 3.7 | Performance: parallel page processing, async AI calls |
| 3.8 | Comprehensive test suite with 20+ real UI screenshots |

## 6. Data Flow Diagram (per element through pipeline)

```
Screenshot: "Login" button at (100, 200, 120, 40)

Stage 1 (AI):   DetectedElement { id:"e01", type:"button", bbox:{x:100,y:200,w:120,h:40},
                                 confidence:0.92, attributes:{cornerRadius:8,
                                 backgroundColor:"#1677FF"} }

Stage 2 (OCR):   OcrLine { text:"登录", bbox:{x:110,y:208,w:100,h:24}, confidence:0.95 }

Stage 3 (Fusion): UnifiedElement {
                    id:"e01", type:"button", bbox:{x:100,y:200,w:120,h:40},
                    text: { content:"登录", ocrBBox:{x:110,y:208,w:100,h:24} },
                    parentId: "card_root",
                    children: []
                  }

Stage 4 (Style):  UnifiedElement {
                    ...above...,
                    visual: {
                      backgroundColor: "#1677FF",
                      textColor: "#FFFFFF",
                      fontSize: 16,
                      fontFamily: "PingFang SC",
                      fontWeight: "500",
                      cornerRadius: 8
                    }
                  }

Stage 5 (Layout): The PARENT (card) gets layout hints.
                  Button itself has no children → no layout.

Stage 6 (Comp):   If there are 3+ identical buttons → ComponentDefinition { name:"PrimaryButton" }

Stage 7 (DSL):    DesignNode {
                    type: "frame", name: "登录",
                    width: 120, height: 40,
                    fills: [{type:"solid", color:"#1677FF"}],
                    cornerRadius: 8,
                    children: [
                      { type:"text", text:"登录", textStyle:"body-medium", ... }
                    ]
                  }

Stage 8 (Figma):  figma.createFrame() → set fills → set cornerRadius →
                    figma.createText() → set characters → append child
```

## 7. API Contract Summary

### Environment Variables

```bash
# Required: LocateAnything model path
LOCATE_ANYTHING_MODEL=/path/to/locate-anything-q8_0.gguf

# Optional: LocateAnything backend (auto-detected if not set)
LOCATE_ANYTHING_DEVICE=cpu      # "cpu" | "cuda" | "metal"
LOCATE_ANYTHING_THREADS=8       # CPU threads for ggml inference
LOCATE_ANYTHING_MODE=hybrid     # "hybrid" | "slow" | "fast"

# Optional for Stage 2 OCR
BAIDU_PADDLE_OCR_TOKEN=...     # If using PaddleOCR remote
# If absent, falls back to local Tesseract

# Optional: YOLO model for fast pre-detection
YOLO_MODEL_PATH=/path/to/yolo-ui-best.pt
YOLO_CONFIDENCE=0.35
YOLO_CLASSES=Image,BackgroundImage,Map,Icon,Modal,Drawer,Button,Input

# Optional for text style precision
TEXT_STYLE_SERVICE_URL=http://127.0.0.1:4120

# Optional for M29 text bbox refinement  
M29EXTRACT_PATH=./bin/m29extract

# Optional for Stage 6 component detection
COMPONENT_MIN_INSTANCES=3
COMPONENT_SIMILARITY_THRESHOLD=0.85
```

### CLI Usage

```bash
# Basic: process one screenshot
codia-design input.png -o output/

# Process multiple screenshots as pages  
codia-design page1.png page2.png page3.png -o output/

# Debug mode: save intermediate results per stage
codia-design input.png -o output/ --debug

# Specify LocateAnything model and backend
codia-design input.png -o output/ \
  --locate-model ./models/locate-anything-q8_0.gguf \
  --locate-device cpu \
  --locate-threads 8

# Specify OCR provider
codia-design input.png -o output/ --ocr tesseract

# Enable YOLO fast pre-detection for common UI elements
codia-design input.png -o output/ --yolo-model ./models/yolo-ui-best.pt

# Output DSL only (skip Figma)
codia-design input.png -o output/ --format dsl

# Help
codia-design --help
```

### Output Structure

```
output/
├── design.dsl.json           # The DesignDSL file
├── assets/
│   ├── img_0001.png          # Cropped image assets
│   ├── img_0002.png
│   └── icon_0001.svg          # Vectorized icons
├── manifest.json             # Metadata about the export
└── debug/                    # (if --debug)
    ├── 01-elements.json
    ├── 02-ocr.json
    ├── 03-fused.json
    ├── 04-styled.json
    ├── 05-layout.json
    ├── 06-components.json
    └── debug-report.html     # Visual debug: original with overlay bboxes
```

## 8. Key Algorithms — Pseudocode

### 8.1 Color Distance

```
function colorDistance(c1: RGB, c2: RGB): number
  return sqrt((c1.r - c2.r)^2 + (c1.g - c2.g)^2 + (c1.b - c2.b)^2)
```

### 8.2 Dominant Color Extraction

```
function dominantColor(pixels: RGB[], excludeColor?: RGB): RGB
  buckets = new Map<string, { count, samples }>()
  for pixel in pixels:
    if excludeColor AND colorDistance(pixel, excludeColor) < 30: skip
    key = floor(pixel.r/16) + ":" + floor(pixel.g/16) + ":" + floor(pixel.b/16)
    buckets[key].count++
    buckets[key].samples.push(pixel)

  bestBucket = max(buckets.values(), by count)
  return median(bestBucket.samples)  // per-channel median
```

### 8.3 Text Color Extraction

```
function textColor(image: RawPixels, textBBox: BBox, backgroundColor: RGB): RGB
  samples = []
  for y in range(textBBox.y, textBBox.y + textBBox.height):
    for x in range(textBBox.x, textBBox.x + textBBox.width):
      pixel = image.getPixel(x, y)
      if pixel.alpha < 200: continue
      dist = colorDistance(pixel, backgroundColor)
      if dist > 40: samples.push({ r: pixel.r, g: pixel.g, b: pixel.b, score: dist })

  if samples is empty: return "#111111"  // fallback dark gray

  // Take top 5% highest-contrast pixels (text pixels, not anti-alias)
  sort(samples, by score, descending)
  topSamples = samples[0..max(1, floor(samples.length * 0.05))]
  avg = average(topSamples)
  return rgbToHex(avg.r, avg.g, avg.b)
```

### 8.4 Corner Radius Detection

```
function cornerRadius(image: RawPixels, elementBBox: BBox, bgColor: RGB): number
  // Check top-left corner
  radius = 0
  for r in range(0, min(elementBBox.width, elementBBox.height) / 2):
    x = elementBBox.x + r
    y = elementBBox.y + r
    pixel = image.getPixel(x, y)
    if colorDistance(pixel, bgColor) > 30:
      radius = r
      break

  // Verify symmetry: check all 4 corners give similar radius
  // (top-right, bottom-left, bottom-right)
  // Return median of 4 corner radii

  return radius
```

### 8.5 Auto Layout Direction Detection

```
function detectDirection(container: BBox, children: BBox[]): "horizontal" | "vertical" | "none"
  if children.length < 2: return "none"

  xs = [child.x for child in children]
  ys = [child.y for child in children]
  xDeltas = [xs[i+1] - xs[i] for i in range(len(xs)-1)]
  yDeltas = [ys[i+1] - ys[i] for i in range(len(ys)-1)]

  xVariance = std(xs) / container.width
  yVariance = std(ys) / container.height

  if xVariance < 0.05 AND yVariance > 0.1: return "vertical"    // same X, different Y
  if yVariance < 0.05 AND xVariance > 0.1: return "horizontal"   // same Y, different X
  if xVariance > 0.2 AND yVariance > 0.2: return "vertical"      // grid → vertical with wrap
  return "none"
```

### 8.6 Structural Hash for Component Detection

```
function structuralHash(node: LayoutNode): string
  childTypes = sort([child.type for child in node.children])
  parts = [
    node.type,
    join(childTypes, ","),
    node.layout?.direction ?? "none",
    round(node.width / max(1, node.height), 2).toString()
  ]
  return join(parts, "|")
```

## 9. Design Decisions and Trade-offs

| Decision | Chosen | Alternative | Rationale |
|----------|--------|------------|-----------|
| Detection engine | LocateAnything-3B (ggml C++) | Claude/GPT API, train YOLO | Zero API cost, 3B params fits consumer hardware, CPU-capable via ggml, native GUI grounding support, box-identical q8_0 quantization |
| Fast pre-detection (optional) | YOLO fine-tuned on UI | LocateAnything only | YOLO is faster (~100ms/img) for common types; LocateAnything handles rare/long-tail elements |
| OCR: remote vs. local | Both (configurable) | Remote only | Tesseract works offline, PaddleOCR better for CJK |
| Icon vectorization | potrace CLI | Custom Rust port | potrace is battle-tested; wrap as subprocess |
| Plugin format | Figma Plugin (in-app) | Standalone web app | Figma Plugin API is the only way to create nodes; web app can't do it |
| Language | Rust (engine) + TS (plugin) + C++ (LocateAnything) | All TypeScript | Rust for speed + single binary deployment; TS required for Figma; C++ for model inference |
| Component detection | Structural hashing | ML clustering | Simple, deterministic, explainable; ML can be added later |
| Layout inference | Heuristic (geometry-based) | ML model | Heuristics work for 80% of UI; ML overkill for MVP |
| Image assets | Crop from source PNG | AI-generated placeholders | Source image has real content; cropping preserves fidelity |
| License | LocateAnything: non-commercial research | Commercial license | NVIDIA License restricts to non-commercial; contact NVIDIA for commercial use |

## 10. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| LocateAnything model returns 0 detections | Low | Detection fails | Fallback to YOLO or edge-detection heuristics |
| LocateAnything hallucinates box positions | Medium | Wrong element placement | Post-processing: clamp boxes to image bounds, filter boxes with implausible aspect ratios |
| OCR unavailable (no token, no Tesseract) | Low | Text missing | Use LocateAnything text detection mode; degrade gracefully |
| Figma Plugin API changes | Low | Plugin breaks | Pin Figma version in plugin manifest; monitor Figma changelog |
| Very large screenshots (> 4K) | Medium | Model rejects | Auto-resize to 2.5K max (model's native limit); scale coordinates back |
| Component detection false positives | Medium | Wrong components | Require >= 3 instances and high similarity; manual review |
| Auto Layout inference incorrect | Medium | Wrong layout | Use absolute positioning as fallback; user can fix in Figma |
| NVIDIA license restricts commercial use | Medium | Can't commercialize | Use for R&D/prototype; contact NVIDIA for commercial license; alternative: train YOLO on UI dataset |
