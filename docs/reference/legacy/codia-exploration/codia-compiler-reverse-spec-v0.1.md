# Codia Compiler Reverse Spec v0.1 + Primary Sample Audit

> Evidence source: this document is derived from direct inspection of raw Codia
> canvas JSON files only:
>
> - `/Users/luhui/Downloads/figma/json/腾讯动漫主要.canvas.json`
> - `docs/reference/codia-samples/tencent-comic-018.canvas.json`
> - `docs/reference/codia-samples/tencent-comic-022.canvas.json`
> - `docs/reference/codia-samples/lizhi-011.canvas.json`
> - `docs/reference/codia-samples/xianyu.canvas.json`
>
> Existing prose/reference documents are intentionally not used as evidence for
> this spec. The goal is to describe the compiler contract visible in Codia's
> own emitted tree, not to repeat prior project conclusions.
>
> Continuation audit constraint: the later "Primary Sample Twenty-Pass Audit"
> section was produced by reading only this document and
> `/Users/luhui/Downloads/figma/json/腾讯动漫主要.canvas.json`. It intentionally
> does not re-open prior reference prose, source code, or the other sample JSONs.
> Treat that section as the current high-detail implementation supplement for
> the primary Tencent comic sample.

## 1. Core Conclusion

Codia's output is not a loose Figma layer dump and it is not just recursive
XY-cut. The observable compiler has a small internal UI-role layer, preserved in
`pluginData[{key:"schema:id"}].value`, and then emits a deliberately simple
visible Figma tree.

The visible tree uses only a few Figma node forms:

| Internal role family | Figma type | Visible name |
|---|---:|---|
| `root` | `FRAME` | `Root` |
| `ViewGroup`, `ListView`, `StatusBar`, `ActionBar`, `BottomNavigation` | `FRAME` | `Groups` |
| `Button` | `FRAME` | `Button` |
| `EditText` | `FRAME` | `Text` |
| `TextView` | `TEXT` | text characters |
| `ImageView` | `ROUNDED_RECTANGLE` | `Image` |
| `Background`, `bg_Button`, `bg_EditText` | `ROUNDED_RECTANGLE` | `Background` |

The important point: visible names are intentionally low-semantic, but the
compiler is not role-blind. `StatusBar`, `ActionBar`, `BottomNavigation`,
`ListView`, `Button`, and `EditText` are all emitted into `schema:id`. A new
Codia-like implementation should preserve an internal role IR even if the final
Figma layer names stay simple.

## 2. Raw Corpus Facts

The real design tree is under:

```text
DOCUMENT "Document"
  CANVAS "Internal Only Canvas"
  CANVAS "Page 1"
    FRAME "Screenshot - <source>.png"
    FRAME "Figma design - <source>.png"
      FRAME "Root"
```

The screenshot frame is not the reconstructed design tree. The design root is
the `Root` frame inside the right-side `Figma design - ...` frame.

Per design root:

| Sample | Size | Root children | Nodes | Frames | Text | Rounded rectangles | Max depth |
|---|---:|---:|---:|---:|---:|---:|---:|
| `腾讯动漫主要` | 665x1440 | 5 | 120 | 38 | 36 | 46 | 5 |
| `tencent-comic-018` | 665x1440 | 3 | 146 | 41 | 48 | 57 | 6 |
| `tencent-comic-022` | 665x1440 | 5 | 120 | 38 | 36 | 46 | 5 |
| `lizhi-011` | 665x1440 | 4 | 93 | 33 | 26 | 34 | 5 |
| `xianyu` | 480x1039 | 9 | 132 | 39 | 40 | 53 | 4 |

Across all five roots: 611 nodes. Every inspected design-root node has both:

```text
guid: {sessionID, localID}
pluginData: [{pluginID, key:"schema:id", value:"..."}]
```

That is a hard identity contract. Do not build a clone where nodes are only
addressed by traversal index, repeated name, or bbox.

## 3. Identity Contract

### 3.1 Figma identity

Every node carries:

```json
{"guid":{"sessionID":2,"localID":120}}
```

This is the Figma-side stable address inside the exported canvas JSON.

### 3.2 Codia compiler identity

Every node also carries:

```json
{
  "pluginData": [
    {
      "pluginID": "1329812760871373657",
      "key": "schema:id",
      "value": "Button_242_9_115"
    }
  ]
}
```

Observed forms:

```text
root_0
ViewGroup_<x>_<y>_<n>
ListView_<x>_<y>_<n>
StatusBar_<x>_<y>_<n>
ActionBar_<x>_<y>_<n>
BottomNavigation_<x>_<y>_<n>
Button_<x>_<y>_<n>
EditText_<x>_<y>_<n>
TextView_<x>_<y>_<n>
ImageView_<x>_<y>_<n>
Background_<x>_<y>_<n>
bg_Button_<x>_<y>_<n>
bg_EditText_<x>_<y>_<n>
ImageView_root_0_2
ImageView_root_1_1
```

For `FRAME` roles, schema x/y exactly matched absolute node x/y in the five
samples. For leaf roles, schema x/y is close but often a few pixels left/up of
the emitted Figma transform:

| Role | Count | dx min/median/max | dy min/median/max | Interpretation |
|---|---:|---:|---:|---|
| `ViewGroup` | 113 | 0 / 0 / 0 | 0 / 0 / 0 | container bbox is compiler bbox |
| `Button` | 37 | 0 / 0 / 0 | 0 / 0 / 0 | control frame bbox is compiler bbox |
| `EditText` | 4 | 0 / 0 / 0 | 0 / 0 / 0 | control frame bbox is compiler bbox |
| `TextView` | 186 | -9 / -3 / 0 | 0 / 0 / 0 | OCR/source bbox differs from Figma text box |
| `ImageView` | 161 | -16 / -4 / 0 | -11 / -3 / 0 | source crop bbox differs from emitted visible rect |
| `bg_Button` | 37 | -8 / -3 / 0 | -6 / -4 / 0 | background source bbox differs from Figma rect |
| `Background` | 32 | -5 / -1.5 / 0 | -4 / -1 / 0 | background source bbox differs from Figma rect |

Implementation implication: store both source/detector bbox and emitted Figma
bbox. Treat `schema:id` coordinates as source evidence coordinates, not as the
only transform truth.

## 4. Coordinate And Node Emission Model

All design-root transforms have identity linear parts:

```text
m00=1, m01=0, m10=0, m11=1
```

Only `m02` and `m12` vary. Coordinates are parent-relative in JSON and compose
to absolute screen coordinates. There is no observed rotation or scale in the
design root nodes.

Frames are transparent containers:

```text
FRAME fillPaints: SOLID black opacity 0
```

Visible backgrounds are not normally parent frame fills. They are emitted as
explicit `ROUNDED_RECTANGLE "Background"` leaf nodes, usually late in the child
array.

## 5. Role Vocabulary

Across the corpus, role counts are:

| Role | Count | Visible output |
|---|---:|---|
| `TextView` | 186 | `TEXT` named by characters |
| `ImageView` | 163 | `ROUNDED_RECTANGLE "Image"` |
| `ViewGroup` | 113 | `FRAME "Groups"` |
| `Button` | 37 | `FRAME "Button"` |
| `bg_Button` | 37 | `ROUNDED_RECTANGLE "Background"` |
| `Background` | 32 | `ROUNDED_RECTANGLE "Background"` |
| `ListView` | 19 | `FRAME "Groups"` |
| `root` | 5 | `FRAME "Root"` |
| `StatusBar` | 4 | `FRAME "Groups"` |
| `EditText` | 4 | `FRAME "Text"` |
| `bg_EditText` | 4 | `ROUNDED_RECTANGLE "Background"` |
| `BottomNavigation` | 4 | `FRAME "Groups"` |
| `ActionBar` | 3 | `FRAME "Groups"` |

This is the compiler's practical type system.

## 6. Naming Rules

Visible Figma names are mechanically derived from internal role:

```text
root                 -> "Root"
ViewGroup/ListView/
StatusBar/ActionBar/
BottomNavigation     -> "Groups"
Button               -> "Button"
EditText             -> "Text"
TextView             -> textData.characters
ImageView            -> "Image"
Background/bg_*      -> "Background"
```

Do not emit broad semantic layer names like `Card`, `Nav`, `SearchBar`,
`Carousel`, `Keyboard`, `PricePlan`, or app-specific names. Codia keeps that
semantic information out of visible layer names.

But do keep internal roles. Flattening everything to `Groups/Image/Text` too
early destroys the compiler evidence that Codia itself preserves.

## 7. Tree Structure Strategy

### 7.1 The tree allows overlap

Codia does not enforce a strict non-overlapping containment tree. Root direct
children can overlap heavily:

```text
t018 root:
  ListView         (0,0,665,1301)
  BottomNavigation (0,1299,665,141)
  Background       (0,1298,665,142)

lizhi root:
  ActionBar        (0,0,665,71)
  BottomNavigation (0,1295,665,145)
  ListView         (0,0,665,1298)
  ImageView        (0,0,665,437)

xianyu root:
  StatusBar        (0,0,480,47)
  ActionBar        (0,48,480,57)
  ViewGroup        (0,106,480,411)
  ...
  ImageView        (0,610,480,61)
  ImageView        (0,0,480,527)
```

This is a major compiler rule. Large background/artwork images may be root or
region siblings of foreground structural groups. A clone that forces every
background to become a parent, or every covered foreground to become its child,
will not match Codia.

### 7.2 Region roles beat pure geometric recursion

Root children are high-level UI regions:

```text
chrome top band:     StatusBar / ActionBar / ViewGroup
content/body:        ListView / ViewGroup
floating rail:       ListView / Background
bottom chrome:       BottomNavigation
large art/background ImageView / Background
keyboard/input area: ViewGroup / ListView / Button / EditText
```

The tree is therefore best understood as:

```text
primitive extraction
-> role classification
-> region segmentation
-> control synthesis
-> repeated collection grouping
-> residual ViewGroup grouping
-> explicit background/image leaf placement
```

Pure XY-cut can help find residual grouping candidates, but it is not the
top-level contract.

## 8. Child Order / Layering Rules

Child order is not simple y/x sorting:

```text
parents with >=2 children: 160
exact y-then-x sorted:      58
exact x-then-y sorted:      44
```

Background order is much more stable:

| Role | Last child count |
|---|---:|
| `bg_Button` | 37/37 |
| `bg_EditText` | 4/4 |
| `Background` | 24/32 |

Practical rule: emit foreground content first, then control/region backgrounds
after it. This matches the JSON child arrays and likely Figma layer-stack
expectations. For ordinary `Background`, last-child is the default, but not a
hard law: some separator/overlapping background pairs appear earlier.

## 9. Primitive Emission Rules

### 9.1 TextView

Observed text node contract:

```text
type: TEXT
name: visible characters
textData.characters: same visible characters
fontName: mostly PingFang SC / Inter
lineHeight: present
fillPaints: SOLID text color
textAutoResize: mostly NONE; sometimes HEIGHT; sometimes missing
```

Text font distribution:

| Font | Count |
|---|---:|
| PingFang SC Regular | 116 |
| Inter Regular | 25 |
| PingFang SC Medium | 18 |
| Inter Light | 11 |
| Inter Semi Bold | 6 |
| PingFang SC Semibold | 6 |
| Inter Medium | 3 |
| Inter Bold | 1 |

Text coordinates are not a pure OCR bbox copy: schema x is often a few pixels
left of emitted x, while y is exact in these samples. A renderer should allow a
font/layout fitting step after OCR detection.

### 9.2 ImageView

Observed image node contract:

```text
type: ROUNDED_RECTANGLE
name: Image
fillPaints[0].type: usually IMAGE
imageScaleMode: FILL
corner radii: absent in all Image examples
strokeWeight: usually 1
```

One `ImageView` in the corpus has a SOLID fill, so visible name is role-driven,
not fill-type-driven.

`IMAGE` fills store `originalImageWidth` and `originalImageHeight`. The emitted
node size can equal original image size or be roughly 1/4 scale; observed image
scale medians are about 3.88x in original pixels per Figma unit, with min 1.0.

### 9.3 Background

`Background` is a role, not a fill type. It can be:

```text
ROUNDED_RECTANGLE "Background" with SOLID fill
ROUNDED_RECTANGLE "Background" with IMAGE fill
```

Across rounded rectangles:

```text
Image + IMAGE:       162
Background + SOLID:   45
Background + IMAGE:   28
Image + SOLID:         1
```

Most image-like backgrounds have no corner radius; solid backgrounds may have
rounded corners, asymmetric corners, stroke paints, or no radius. Do not decide
`Image` vs `Background` from paint type alone.

## 10. Controls

### 10.1 Button

`Button` is a transparent frame with a dedicated `bg_Button` leaf. It is not
just a text bbox wrapper.

Observed modes across 37 buttons:

| Mode | Count | Example |
|---|---:|---|
| 1 text + 0 image + background | 16 | payment button, tags, send |
| 1 text + 1 image + background | 12 | status URL pill, icon/text shortcuts |
| 2 text + 0 image + background | 9 | numeric keyboard key, e.g. `1` + `@/.` |

All 37 `bg_Button` nodes are the last child of their `Button` parent.

Button frame vs child-union margins:

| Margin | min | median | max |
|---|---:|---:|---:|
| parent left outside union | -8 | -3 | 0 |
| parent top outside union | -6 | -4 | 0 |
| union right beyond parent | -3 | -2 | 0 |
| union bottom beyond parent | -3 | -1 | 0 |

The negative signs mean the parent frame is slightly larger than the union of
children. Typical button padding is small but real. Do not synthesize button
frames as exact child union.

Button backgrounds can be solid or image fills:

```text
IMAGE: 8
#fefefe: 8
#a8b1b9: 4
plus one-off sampled colors
```

Button recognition rule for a clone:

```text
Button candidate =
  compact foreground text cluster
  + explicit source background evidence behind it
  + optional icon/image sibling
  + tight parent frame around the source control bbox
```

Do not create structural buttons from text bbox alone. Codia's emitted buttons
always have `bg_Button` evidence.

### 10.2 EditText

`EditText` is emitted visibly as `FRAME "Text"` and internally as
`EditText_<x>_<y>_<n>`.

Observed modes:

```text
icon + bg_EditText
query text + placeholder text + icon + bg_EditText
typed text + small cursor Background + bg_EditText
```

All 4 `bg_EditText` nodes are the last child of the `EditText` parent. Like
Button, EditText should be built from actual background/source evidence plus
text/icon members, not from a text bbox alone.

## 11. Chrome Roles

### 11.1 StatusBar

Observed `StatusBar` pattern:

```text
FRAME "Groups" / StatusBar
  TextView time
  Button URL pill
  ImageView signal-like icon
  ImageView wifi/battery-like icon
  ImageView battery-like icon
```

There are 4 `StatusBar` nodes. They live at y=0 and contain exactly this
five-child pattern in these samples.

### 11.2 ActionBar

`ActionBar` is less uniform:

```text
t018: top browser/status-like bar with time, URL pill, icons
lizhi: wrapper containing StatusBar
xianyu: search/action row containing back icon, EditText, action icons
```

So `ActionBar` should not be hardcoded as "top status bar". It is a top chrome
band role: a horizontal control/action region near the top, sometimes wrapping
StatusBar, sometimes a search/action row.

### 11.3 BottomNavigation

`BottomNavigation` is always root child in the five samples. It may contain:

```text
one nested ViewGroup containing tab items and backgrounds
or direct ViewGroup tab items plus Background
or a top separator ViewGroup plus the tab row ViewGroup
```

Tab items are emitted as `ViewGroup "Groups"` with `ImageView + TextView`.
Bottom navigation backgrounds are explicit `Background` leaves, often last.

## 12. Collection And Region Roles

### 12.1 ListView

`ListView` is not just a literal vertical list. It marks repeated or scrollable
collections and large content regions. Observed examples include:

```text
horizontal category tabs
vertical floating side rail
main content body
horizontal image strip
price-plan cards
gift/reward tiles
keyboard suggestion strip
```

`ListView` fanout ranges from 2 to 11. It often contains repeated `ViewGroup`
children, but can also contain direct `TextView`, `ImageView`, nested `ListView`,
`ActionBar`, `Button`, and `Background`.

`ListView` is allowed to have child overflow:

```text
child containment violations: 2/85
left margin min:  -23
right margin min: -10
```

Implementation rule: use `ListView` when a group has repetition/scroll/body
evidence, not merely because it is a container. It can be horizontal or vertical.

### 12.2 ViewGroup

`ViewGroup` is the generic structural frame. It covers:

```text
single-text nav item wrappers
image+text tab items
cards/tiles with foreground and background
large content regions
rows with many text/image leaves
keyboard columns/rows
fallback residual groups
```

`ViewGroup` fanout ranges from 1 to 18. Its bbox is not simply union(children)
plus a constant padding:

```text
left margin min/median/max:   -9 / 19 / 181
top margin min/median/max:    -5 / 11 / 76
right margin min/median/max:  -35 / 16 / 486
bottom margin min/median/max: -5 / 11 / 151
```

This means Codia often uses recognized region bounds, source background bounds,
or repeated-item cell bounds instead of only child union.

Implementation rule: compute `ViewGroup` bbox from the strongest region
evidence in this order:

```text
source background / source image region
recognized control/list/item cell
repeated grid/list cell slot
foreground child union with small padding
residual spatial group bbox
```

## 13. Background Placement Rules

Background leaves appear in three forms:

```text
bg_Button      owned by Button
bg_EditText    owned by EditText
Background     generic region/root/card/keyboard/background leaf
```

Control backgrounds are always children of their owner and always last.

Generic backgrounds are more flexible:

```text
parent=ViewGroup:        26
parent=root:              3
parent=ListView:          1
parent=BottomNavigation:  1
parent=EditText:          1 cursor-like small background
```

Generic `Background` is last in 24/32 cases. Non-last cases are mostly paired
thin separators, cursor-like marks, or complex keyboard/card background
composition.

Important negative rule: a large image/background can be a sibling of the group
it visually supports. Do not force visual background into containment ownership
if Codia would keep it as a sibling.

## 14. Page Segmentation Strategy

A Codia-like compiler should first identify high-confidence screen regions:

1. Root canvas bounds.
2. Top chrome bands: status/action/search bars.
3. Bottom chrome bands: bottom navigation, keyboard/input zones.
4. Main scroll/content body.
5. Floating rails/overlays.
6. Large root-level image/background assets.

Then run lower-level grouping inside these regions.

This explains the root direct children better than pure recursive whitespace:
Codia keeps top chrome, body, bottom chrome, and large image/background strata as
separate root children, even when they overlap.

## 15. Proposed Compiler Pipeline

The minimal clone architecture should be:

```text
1. Decode screenshot and normalize scale.
2. Extract source primitives:
   - OCR text boxes with font/color estimates.
   - image/crop candidates with source pixels.
   - solid/rounded background candidates.
   - thin separators/cursors/scrollbar-like marks.
3. Assign every primitive a stable source id and source bbox.
4. Classify primitive roles:
   - TextView, ImageView, Background.
5. Detect controls before generic grouping:
   - Button = bg_Button + text(s) + optional image.
   - EditText = bg_EditText + text(s)/placeholder + optional icon/cursor.
6. Detect chrome/region roles:
   - StatusBar, ActionBar, BottomNavigation.
   - keyboard/input panel as ViewGroup/ListView/Button structures.
7. Detect repeated collections:
   - horizontal/vertical repeated cells -> ListView.
   - each cell -> ViewGroup/Button/EditText as appropriate.
8. Build residual ViewGroups:
   - source region bounds first.
   - repeated cell bounds second.
   - foreground union with padding only as fallback.
9. Place large backgrounds/images:
   - as owner child when tightly owned by a control/card.
   - as sibling/root child when it functions as region backdrop/artwork.
10. Sort children:
   - structural/foreground content first.
   - backgrounds and large cover images later.
   - do not rely on y/x sort as the only ordering.
11. Emit Figma nodes:
   - visible names from role mapping.
   - transparent frames for containers.
   - explicit rounded rectangles for image/background leaves.
   - `guid` equivalent and `schema:id` equivalent for every node.
```

## 16. What Not To Build

Do not build a clone around these false contracts:

```text
false: Codia is just xycut.
true:  Codia has an internal role layer and region/control/list passes.

false: Visible name "Groups" means no role.
true:  Many "Groups" have distinct internal roles in schema:id.

false: Background fill type determines Image vs Background.
true:  Role determines visible name; Background can be IMAGE, Image can be SOLID.

false: A parent bbox is always child union plus fixed padding.
true:  Region/source/list-cell bounds frequently dominate.

false: A valid tree must be non-overlapping.
true:  Root and region children can overlap heavily.

false: Text bbox can synthesize a structural button background.
true:  Observed Button/EditText nodes always have explicit background evidence.

false: Child order is top-left sorted.
true:  Background/control backplates are deliberately emitted late.
```

## 17. Validation Targets For A Reimplementation

A new compiler should be judged against the raw Codia samples with these checks:

1. Every emitted node has stable identity: source id, normalized id, and Figma
   export id if available.
2. Visible node vocabulary is limited to `Root`, `Groups`, `Button`, `Text`,
   `Image`, `Background`, and text characters.
3. Internal role vocabulary can reproduce the observed role counts and parent
   distributions.
4. Buttons match the three observed modes:
   - text + background
   - text + icon + background
   - two text nodes + background
5. `bg_Button` and `bg_EditText` are owner children and last.
6. Bottom navigation tab items become `ViewGroup` items, not semantic `Tab`
   nodes.
7. Large background/artwork can remain sibling to foreground structural groups.
8. Root direct regions may overlap.
9. Container bboxes are compared by role-aware evidence, not by child-union
   formula alone.
10. Evaluation must include both:
    - Codia container recall.
    - Go/compiler container precision by internal role.

## 18. Open Questions

These cannot be settled from five JSON samples alone:

1. The exact classifier boundary between `ViewGroup` and `ListView`.
   Repetition is strongly correlated with `ListView`, but not sufficient as a
   complete rule because some `ListView` nodes are large mixed content bodies.
2. The exact boundary between root-level `ImageView` and root-level
   `Background`. Both can visually act as backdrops.
3. Whether `StatusBar` and browser URL pill emission are Codia/plugin chrome
   artifacts, source screenshot artifacts, or a combination.
4. How `blobs[*].bytes` map to vector/path data. The design trees reference
   image hashes directly; blob decoding was not required for the structural
   conclusions here.
5. Whether additional app categories introduce more internal roles beyond the
   observed vocabulary.

These should be resolved by adding more raw `.canvas.json` exports and rerunning
the same role/tree/background/order analysis, not by weakening the compiler
contract into generic threshold guessing.

## 19. Primary Sample Twenty-Pass Audit

This section completes the spec against the primary file only:

```text
/Users/luhui/Downloads/figma/json/腾讯动漫主要.canvas.json
```

The primary sample is internally named `腾讯动漫_022_1440.png` in the canvas:

```text
Page 1
  FRAME "Screenshot - 腾讯动漫_022_1440.png"
  FRAME "Figma design - 腾讯动漫_022_1440.png"
    FRAME "Root"
```

The design root has 120 nodes, max depth 5, and 5 root children.

### Pass 1: Canvas Envelope And Target Root

Facts:

```text
top keys: blobs, root, version
version: 101
blobs: 160
document root: DOCUMENT "Document"
page children:
  FRAME "Screenshot - 腾讯动漫_022_1440.png"
  FRAME "Figma design - 腾讯动漫_022_1440.png"
design root:
  FRAME "Root" size=665x1440 children=5
```

Compiler contract:

1. The compiler output should be a design-root subtree under a wrapper frame,
   not a mutation of the screenshot frame.
2. Any evaluator must select `Figma design - ... / Root`, not the screenshot
   side-by-side frame.
3. The root frame size is the reconstructed screenshot viewport size.

### Pass 2: Identity Is Mandatory, Not Optional Metadata

Facts:

```text
design-root nodes: 120
guid coverage:     120/120
schema:id coverage:120/120
pluginID:          1329812760871373657 on all 120 schema:id entries
duplicate guid:    none
duplicate schema:  none
```

Compiler contract:

1. Every emitted node needs two identities:
   - export identity equivalent to `guid.sessionID:guid.localID`;
   - compiler identity equivalent to `schema:id`.
2. `schema:id` must be unique inside a design root.
3. A clone that cannot answer "which compiler node created this Figma node" is
   not Codia-like, even if the visual tree looks similar.

### Pass 3: Visible Vocabulary Is Closed

Facts:

```text
Figma types:
  ROUNDED_RECTANGLE: 46
  FRAME:             38
  TEXT:              36

top visible names:
  Image:      37
  Groups:     32
  Background:  9
  Button:      4
  Root:        1
  Text:        1
  text content names for all TEXT nodes
```

Compiler contract:

1. Do not emit visible semantic names such as `Card`, `Tab`, `Search`,
   `Carousel`, `Ranking`, or `BottomNav`.
2. The final visible vocabulary for this sample is:

```text
Root, Groups, Button, Text, Image, Background, and literal text strings
```

3. Extra semantic names belong in internal role/evidence metadata, not in
   visible Figma layer names.

### Pass 4: Internal Role Mapping Is Deterministic

Facts from the primary root:

| Role | Count | Visible type/name |
|---|---:|---|
| `ImageView` | 37 | `ROUNDED_RECTANGLE "Image"` |
| `TextView` | 36 | `TEXT "<characters>"` |
| `ViewGroup` | 25 | `FRAME "Groups"` |
| `ListView` | 5 | `FRAME "Groups"` |
| `Button` | 4 | `FRAME "Button"` |
| `bg_Button` | 4 | `ROUNDED_RECTANGLE "Background"` |
| `Background` | 4 | `ROUNDED_RECTANGLE "Background"` |
| `root` | 1 | `FRAME "Root"` |
| `StatusBar` | 1 | `FRAME "Groups"` |
| `EditText` | 1 | `FRAME "Text"` |
| `bg_EditText` | 1 | `ROUNDED_RECTANGLE "Background"` |
| `BottomNavigation` | 1 | `FRAME "Groups"` |

Compiler contract:

1. The role must be assigned before visible name emission.
2. `Groups` is not a type. It is the visible name for several roles.
3. `Background` is not a paint style. It is the visible name for multiple
   internal background roles.

### Pass 5: Root Segmentation Is A Role Graph

Primary root direct children:

```text
0 /0 ViewGroup        FRAME "Groups"     (0,0,665,236)     children=4
1 /1 ListView         FRAME "Groups"     (580,279,62,1026) children=2
2 /2 ListView         FRAME "Groups"     (0,160,665,1179)  children=3
3 /3 Background       ROUNDED_RECTANGLE "Background" (654,237,6,36) children=0
4 /4 BottomNavigation FRAME "Groups"     (0,1284,665,156)  children=1
```

Compiler contract:

1. Root segmentation must run before residual spatial grouping.
2. The root is not a clean vertical stack. It contains overlapping regions:
   top band, side rail, main content body, floating/slim background, and bottom
   navigation.
3. A root-level `Background` can be a standalone sibling, not a child of the
   nearby foreground region.

### Pass 6: `schema:id` Coordinates Preserve Source Bboxes

Primary deltas between schema x/y and emitted absolute Figma x/y:

| Role | dx min/median/max | dy min/median/max |
|---|---:|---:|
| `ViewGroup` | 0 / 0 / 0 | 0 / 0 / 0 |
| `Button` | 0 / 0 / 0 | 0 / 0 / 0 |
| `EditText` | 0 / 0 / 0 | 0 / 0 / 0 |
| `TextView` | -6 / -3 / 0 | 0 / 0 / 0 |
| `ImageView` | -7 / -4 / 0 | -6 / -3 / 0 |
| `ListView` | -12 / 2 / 23 | -58 / -15 / -1 |
| `Background` | -4 / -1 / 0 | -3 / -0.5 / 0 |
| `bg_Button` | -8 / -4 / -2 | -6 / -6 / 0 |
| `bg_EditText` | -6 / -6 / -6 | -6 / -6 / -6 |

Compiler contract:

1. Store `sourceBBox` and `emittedBBox` separately.
2. Frame-like structural roles often use source bbox directly.
3. Leaf roles may be adjusted by font fitting, crop fitting, stroke/radius
   fitting, or visual-edge trimming.
4. Do not round-trip a clone through only emitted Figma coordinates and expect
   to recover the source detector contract.

### Pass 7: Transform Model Is Translation-Only

Facts:

```text
all 120 design-root nodes:
  m00=1, m01=0, m10=0, m11=1
  only m02/m12 vary
```

Compiler contract:

1. Emit translation-only transforms for this class of output.
2. Rotation, scaling, skew, and nested transforms with non-identity linear
   parts are outside the observed contract for this sample.
3. Parent-relative transforms must compose to the absolute bboxes used by
   `schema:id` analysis.

### Pass 8: Frame Style Has A Root Exception

Facts:

```text
FRAME count: 38
non-root transparent frames:
  fill: SOLID black opacity 0
  opacity: 1
  strokeWeight: 1
  strokeAlign: INSIDE
  strokeJoin: MITER
  frameMaskDisabled: true
root frame:
  fill: #f2f9fe opacity 1
  horizontalConstraint: STRETCH
```

Compiler contract:

1. All structural child frames should be transparent containers.
2. The root frame can carry a real fill sampled from the screen/background.
3. Do not infer structural visibility from frame fill, because transparent
   frames still carry role, bbox, identity, and grouping semantics.

### Pass 9: Text Emission Contract

Facts:

```text
TextView count: 36
font families/styles:
  PingFang SC Regular:   26
  PingFang SC Medium:     6
  Inter Regular:          2
  Inter Semi Bold:        1
  PingFang SC Semibold:   1
textAutoResize:
  NONE:   35
  HEIGHT:  1
textAlignVertical: CENTER on 36/36
lineHeight: 100 PERCENT on 36/36
letterSpacing: 0 PERCENT on 36/36
leadingTrim: NONE on 36/36
name == textData.characters on 36/36
```

Compiler contract:

1. Text node name and text characters must match.
2. Vertical alignment is part of the emitted Figma contract, not an arbitrary
   renderer default.
3. Font selection is conservative: system UI fonts, mostly PingFang SC for
   Chinese text and Inter for status-like Latin/digit text.
4. OCR bbox is not enough. The compiler needs a text fitting pass that chooses
   font, size, emitted bbox, and color.

### Pass 10: Image Fill Contract

Facts:

```text
IMAGE fills: 41
  ImageView:  37
  Background:  3
  bg_Button:   1
unique image hashes: 41
imageScaleMode: FILL in observed image fill objects
original-to-emitted scale:
  width  min/median/max: 1.0 / 3.826 / 4.122
  height min/median/max: 1.0 / 3.833 / 4.125
```

Compiler contract:

1. Image assets must be real crop/image fills with stable hashes or equivalent
   asset IDs.
2. `ImageView` usually maps to an image fill, but `Background` and `bg_Button`
   can also map to image fills.
3. Store original image dimensions. They are part of the emitted artifact and
   useful for validating scale/crop fidelity.
4. Do not classify by fill type alone.

### Pass 11: Rounded Rectangle Style Contract

Primary rounded roles:

```text
ImageView:
  37 nodes, all name=Image, fill=IMAGE, no corner radii, strokeWeight=1

Background:
  3 image-fill nodes, no corner radii, strokeWeight=1
  1 solid #fefefe node, no corner radii, strokeWeight=1

bg_Button:
  #f6f7f6 radius=16 strokeWeight=0
  #f5f5f5 radius=27 strokeWeight=1
  #f6f6f6 radius=28.5 strokeWeight=1
  IMAGE no radii strokeWeight=1

bg_EditText:
  #f4f4f4 radius=25 strokeWeight=0
```

Compiler contract:

1. Radius belongs to the fitted background/control surface, not to the parent
   frame.
2. Image-like backgrounds often have no explicit radii because the raster crop
   already contains the shape.
3. Solid control backgrounds need sampled color, radius, stroke weight, and
   optional stroke paint.

### Pass 12: Button Synthesis

Primary buttons:

```text
/0/0/1  Button (242,9,177,50)
  TextView "uinotes.com"
  ImageView icon
  bg_Button #f6f7f6 radius=16

/0/2/1  Button (496,154,65,62)
  TextView "游戏"
  ImageView icon
  bg_Button #f5f5f5 radius=27

/0/2/2  Button (577,154,63,63)
  TextView "周边"
  ImageView icon
  bg_Button #f6f6f6 radius=28.5

/1/1/1  Button (557,1229,95,28)
  TextView "归签到"
  ImageView icon
  bg_Button IMAGE
```

All four buttons have:

```text
children=3
child order: TextView, ImageView, bg_Button
bg_Button index: last child
frame margins around child union:
  left 2..8, top 0..6, right 0..3, bottom 0..3
```

Compiler contract:

1. In this sample, `Button` means text + icon + backplate.
2. Button creation must happen before generic grouping; otherwise these will
   degrade into arbitrary three-child spatial groups.
3. `bg_Button` is owner-local and last, even though it visually sits behind
   foreground children.

### Pass 13: EditText Synthesis

Primary EditText:

```text
/0/2/0 EditText (22,155,461,66), visible name "Text"
  ImageView search/icon (51,177,24,24)
  bg_EditText (28,161,452,57), #f4f4f4 radius=25
```

Facts:

```text
children=2
child order: ImageView, bg_EditText
bg_EditText is last child
frame margins around child union: left=6 top=6 right=3 bottom=3
```

Compiler contract:

1. Empty/search input can be represented without a `TextView` child.
2. `EditText` is still a structural control frame because it has a fitted
   `bg_EditText` and an input icon.
3. Do not require placeholder OCR text to create an editable/search container.

### Pass 14: Top Chrome Contract

Primary top chrome:

```text
/0 ViewGroup (0,0,665,236)
  /0/0 StatusBar (0,0,665,67)
    TextView "11:02"
    Button URL pill
    ImageView
    ImageView
    ImageView
  /0/1 ListView category tabs
  /0/2 ViewGroup search/actions
  /0/3 Background top-band raster
```

Compiler contract:

1. Top chrome is not just the status bar. In this sample it is a parent
   `ViewGroup` containing status, tab list, search/action row, and background.
2. `StatusBar` is a child role inside the top region, not necessarily a root
   child.
3. The top-band background is a sibling of foreground chrome children and is
   last inside `/0`.

### Pass 15: Bottom Navigation Contract

Primary bottom navigation:

```text
/4 BottomNavigation (0,1284,665,156)
  /4/0 ViewGroup (0,1298,665,141)
    five tab ViewGroups
    Background home indicator image (215,1418,235,8)
    Background white nav backplate (0,1298,665,141)
```

Each tab item:

```text
ViewGroup
  ImageView icon
  TextView label
```

Tab labels:

```text
推荐, 圈子, V会员, 书架, 我的
```

Compiler contract:

1. Bottom navigation is a role frame at root level.
2. It may contain an intermediate `ViewGroup` row rather than direct tab items.
3. Tab items are not emitted as `Button`; they are generic `ViewGroup`
   containers with image + text.
4. The home indicator and nav backplate are explicit `Background` nodes and are
   emitted after tab items.

### Pass 16: ListView Is Multi-Pattern

Primary `ListView` nodes:

```text
/0/1  category tabs         (12,71,630,76), children=7
/1    floating side rail    (580,279,62,1026), children=2, child overflow
/1/1  nested side list      (557,396,95,897), children=2
/2    main content body     (0,160,665,1179), children=3
/2/2  horizontal strip      (26,1269,619,29), children=3
```

Compiler contract:

1. `ListView` can be horizontal, vertical, nested, or a large body region.
2. Repetition is strong evidence but not the only evidence; `/2` is a main body
   list-like region with mixed child roles.
3. `ListView` may allow child overflow. `/1` has child `/1/1` at x=557, wider
   than its parent x=580..642.
4. The role should be assigned by collection/scroll/rail/body behavior, not by
   a fixed fanout threshold.

### Pass 17: ViewGroup Is Residual But Not Disposable

Primary `ViewGroup` patterns:

```text
top chrome region:          /0
single text tab wrappers:   /0/1/1..5
search action row:          /0/2
side rail image groups:     /1/1/0, /1/1/0/0, /1/1/0/1
main content rows/cards:    /2/0, /2/0/0..3, /2/1
image strip item wrappers:  /2/2/0..2
bottom nav row/items:       /4/0, /4/0/0..4
```

Observed fanout ranges from 1 to 12 in the primary sample.

Compiler contract:

1. `ViewGroup` is the general structural fallback after specific role passes.
2. Do not collapse `ViewGroup` merely because it has one child. Single-child
   text tab wrappers are real Codia nodes in `/0/1/1..5`.
3. Do not preserve every residual group blindly either. The preservation
   criterion is source region/cell/control evidence, not child count alone.

### Pass 18: Containment And Overlap Are Deliberate

Primary containment violations:

```text
/1 ListView child /1/1 ListView overflows horizontally
/2/0 ViewGroup children /2/0/0 and /2/0/3 overflow right
/2/1 ViewGroup child /2/1/2 ImageView starts above parent top
```

High-overlap sibling cases include:

```text
root:
  /1 ListView overlaps /2 ListView
  /2 ListView overlaps /3 Background

/0:
  StatusBar/ListView/search row all overlap /0/3 Background

controls:
  TextView/ImageView overlap bg_Button or bg_EditText by design

/2/0/0:
  large ImageView background overlaps many TextView/ImageView leaves

/4/0:
  tab ViewGroups overlap nav backplate Background
```

Compiler contract:

1. The tree is an ownership/drawing contract, not a strict geometry nesting
   tree.
2. Parent-child and sibling relations must allow overlap and controlled
   overflow.
3. Background ownership is role-specific. Some backgrounds are owned by a
   control, some by a region, and some remain root-level siblings.

### Pass 19: Child Order Is Foreground-Then-Backplate

Primary order facts:

```text
parents with >=2 children: 27
exact y-then-x sorted:     11
exact x-then-y sorted:     10

background indices:
  root:        Background at index 3 of 5
  /0:          Background at index 3 of 4
  Button:      bg_Button last in all 4
  EditText:    bg_EditText last
  /4/0:        Background nodes at indices 5 and 6 of 7
```

Compiler contract:

1. Child order is not a geometry sort.
2. Emit foreground/structural children first, then visual backplates.
3. For controls, owner-local background is always last in this sample.
4. For regions, background is usually late, but can appear before later
   unrelated root children.

### Pass 20: Schema Numbering Encodes Generation Order

Primary schema numbering:

```text
schema suffix range: 0..119
unique suffixes:     120/120
root:                root_0
lowest non-root:     BottomNavigation_0_1284_1
highest suffixes:    top status bar subtree, ending TextView_69_28_119
```

Ascending suffixes begin in bottom navigation:

```text
1  BottomNavigation_0_1284_1
2  ViewGroup_0_1298_2
3  Background_0_1298_3
4  Background_211_1415_4
5  ViewGroup_532_1299_5
...
```

Descending high suffixes are top chrome/status:

```text
119 TextView_69_28_119
118 TextView_283_24_118
117 ImageView_256_21_117
116 bg_Button_242_9_116
115 Button_242_9_115
114 ImageView_482_43_114
113 ImageView_529_29_113
112 ImageView_568_29_112
111 StatusBar_0_0_111
```

Compiler contract:

1. The numeric suffix is not random. It is a unique per-root compiler sequence.
2. The primary sample suggests bottom-up or reverse visual traversal generation:
   bottom navigation receives low numbers while top status receives high
   numbers.
3. A clone should produce stable deterministic numbering, even if the exact
   traversal order is not yet fully specified.
4. Evaluators should not use suffix order as geometry truth, but debuggers
   should preserve it because it exposes compiler creation order.

## 20. Primary Sample Implementation Blueprint

For the primary Tencent comic sample, a Codia-like compiler should proceed in
this concrete order:

```text
1. Build Root frame 665x1440 with sampled root fill.
2. Extract all source primitives with stable source bboxes and source IDs.
3. Emit leaf candidates as TextView, ImageView, Background source objects.
4. Fit text nodes: font, size, color, emitted bbox, textData.characters.
5. Fit image/background rounded rectangles: crop asset, original dimensions,
   fill type, radius, stroke.
6. Synthesize controls:
   - Status URL pill Button.
   - Search/action row icon Buttons.
   - Floating side rail Button.
   - Search EditText without placeholder text.
7. Segment top chrome as ViewGroup /0:
   - StatusBar.
   - category tab ListView.
   - search/action ViewGroup.
   - top-band Background last.
8. Segment floating side rail as root ListView /1, allowing horizontal child
   overflow.
9. Segment main body as root ListView /2:
   - ranking/card region ViewGroup /2/0.
   - promotion row ViewGroup /2/1.
   - bottom horizontal image strip ListView /2/2.
10. Segment bottom navigation as root BottomNavigation /4 with nested ViewGroup
    row and five tab item ViewGroups.
11. Place root-level slim Background /3 as a sibling, not as a child of /2.
12. Sort each parent by role-layering:
    foreground structural children first, background/backplate leaves late.
13. Assign deterministic `schema:id` values and Figma `guid` equivalents to
    every node.
```

The decisive rule is that every structural node must have one of these evidence
classes:

```text
chrome-role evidence
control-role evidence
collection/list evidence
source background/image region evidence
repeated cell/slot evidence
residual grouped foreground evidence
```

Child count alone is not evidence. Pure whitespace splitting alone is not
evidence. Text bbox alone is not evidence.

## 21. Primary Sample Completion Checklist

Use this checklist when implementing or auditing a clone against
`腾讯动漫主要.canvas.json`:

1. Design root found at `Figma design - 腾讯动漫_022_1440.png / Root`.
2. Root has size `665x1440`.
3. Emitted design-root node count can explain the Codia count of 120.
4. Every node has stable export identity and compiler identity.
5. Visible type set is limited to `FRAME`, `TEXT`, `ROUNDED_RECTANGLE`.
6. Visible non-text names are limited to `Root`, `Groups`, `Button`, `Text`,
   `Image`, `Background`.
7. Internal role counts are explainable: 37 `ImageView`, 36 `TextView`, 25
   `ViewGroup`, 5 `ListView`, 4 `Button`, 1 `StatusBar`, 1 `EditText`, 1
   `BottomNavigation`, and background roles.
8. Root direct children match the five-region pattern:
   top region, side rail, main body, slim background, bottom navigation.
9. Top region `/0` contains status, category list, search/actions, background.
10. Category tabs use single-child `ViewGroup` wrappers for selected/unselected
    labels.
11. Search box is `EditText` with icon + `bg_EditText`, even with no text child.
12. Buttons have text + icon + `bg_Button`, with `bg_Button` last.
13. Main content body is `ListView`, not just a `ViewGroup`.
14. Main ranking/card rows preserve large image/background overlap.
15. Side rail permits child overflow.
16. Bottom nav is `BottomNavigation` with nested `ViewGroup` row.
17. Bottom nav tab items are `ViewGroup`, not `Button`.
18. Background nodes may be image fills or solid fills.
19. Child ordering follows foreground-then-background layering, not x/y sort.
20. `schema:id` suffixes are unique and deterministic.

If any of these fail, the clone is not yet matching the primary Codia compiler
contract, even if a rendered screenshot looks visually close.
