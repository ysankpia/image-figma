# 059 Image Math Dependencies And Boundary Hardening

- 状态：active
- 创建日期：2026-05-26
- 负责人：Codex

## Goal

第一轮升级只建立 image math 执行层和防越权边界，不迁移生产行为。

目标是让 Pillow、NumPy、scikit-image、orjson 和 rich 可以进入仓库，但只能按明确合同使用：

```text
Pillow / NumPy / scikit-image = image math execution dependencies
orjson = JSON serialization implementation behind one wrapper
rich = dev/script-only dependency
```

这轮不是 Codia 级最终拆图能力，不改变 DSL、M29.5 replay plan、cleanup authorization、materializer、Renderer 或 Figma plugin 行为。

## First-Principles Contract

Real goal:

```text
从像素世界恢复设计世界时，把高成本像素数学从领域判断里隔离出来。
```

Source truth:

```text
source PNG pixels
-> raw M29 primitive evidence
-> M29.2 source ownership
-> M29.3 relation graph
-> M29.5 replay / cleanup authorization
-> materializer plan consumption
```

Information-loss point:

```text
当前 report-only 图像热点仍有手写像素循环和局部启发式。直接替换生产逻辑会把性能优化、算法漂移和 ownership 决策混在一起。
```

Owning layer:

```text
backend/app/image_math/ owns arrays, masks, components, morphology, alpha bytes, background maps, and low-level metrics.
M29.2 still owns pixelOwner / visualKind / replayDecision.
M29.5 still owns visible replay order and cleanup authorization.
plan_materializer still only consumes M29.5 plan.
```

Do not do:

```text
do not let Pillow / NumPy / scikit-image decide pixelOwner
do not let image_math decide replayDecision or cleanup authorization
do not create DSL nodes from image_math
do not migrate media_internal_decomposition or transparent_asset_report production behavior in this first round
do not add text, filename, path, theme, coordinate, bbox, sample-id, or screenshot-specific rules
```

## Scope

包含：

- 新增 ADR 0074，固定 image_math execution dependency 边界。
- 新增 `docs/architecture/image_math_boundary.md`。
- 新增 `docs/checklists/m29-runtime-fact-check.md`。
- 更新依赖策略和文档索引。
- 引入 backend runtime dependencies：Pillow、numpy、scikit-image、orjson。
- 引入 backend dev dependency：rich。
- 新增 `backend/app/json_tools.py`，统一封装 orjson。
- 新增 `backend/app/image_math/` 纯执行层。
- 新增 image_math 单元测试和 import-boundary 测试。
- 运行 backend 全量回归，证明 behavior invariant。

不包含：

- 不迁移 `media_internal_decomposition/candidates.py` 生产逻辑。
- 不迁移 `transparent_asset_report/alpha.py` 生产逻辑。
- 不迁移 `visual_primitive/components.py` 或 `png_tools/sampling.py` 生产逻辑。
- 不新增 EvidenceScore 生产决策。
- 不改变 M29.5 replay plan 输出。
- 不改变 cleanup 行为。
- 不改变 materializer、Renderer、Figma plugin。
- 不新增 Auto Layout、Component、Variant、Variables 或 vectorization。

## Stages

### Stage 0: Contract And Documentation

改动：

```text
docs/plans/active/059-image-math-dependencies-and-boundary-hardening.md
docs/decisions/0074-introduce-image-math-execution-dependencies.md
docs/architecture/image_math_boundary.md
docs/checklists/m29-runtime-fact-check.md
docs/engineering/dependency-policy.md
docs/index.md
```

验证：

```bash
git diff --check
```

提交：

```text
docs: define image math execution boundary
```

### Stage 1: Dependencies And JSON Boundary

改动：

```text
backend/pyproject.toml
backend/uv.lock
backend/app/json_tools.py
backend/tests/test_json_tools.py
```

验证：

```bash
cd backend
uv sync
uv run pytest tests/test_json_tools.py -q
```

提交：

```text
feat: add json tools and image math dependencies
```

### Stage 2: Isolated Image Math Execution Layer

新增：

```text
backend/app/image_math/__init__.py
backend/app/image_math/arrays.py
backend/app/image_math/background.py
backend/app/image_math/masks.py
backend/app/image_math/morphology.py
backend/app/image_math/components.py
backend/app/image_math/alpha.py
backend/app/image_math/debug.py
backend/app/image_math/metrics.py
backend/tests/test_image_math_arrays.py
backend/tests/test_image_math_masks.py
backend/tests/test_image_math_components.py
backend/tests/test_image_math_alpha.py
```

验证：

```bash
cd backend
uv run pytest \
  tests/test_image_math_arrays.py \
  tests/test_image_math_masks.py \
  tests/test_image_math_components.py \
  tests/test_image_math_alpha.py \
  -q
```

提交：

```text
feat: add isolated image math execution layer
```

### Stage 3: Import Boundary Enforcement

新增：

```text
backend/tests/test_image_math_import_boundaries.py
```

验证：

```bash
cd backend
uv run pytest tests/test_image_math_import_boundaries.py -q
```

提交：

```text
test: enforce image math import boundaries
```

### Stage 4: Behavior-Invariant Regression

验证：

```bash
cd backend
uv run pytest -q
git diff --check
git status --short --branch
```

如前端依赖状态允许，补充：

```bash
pnpm run check
```

提交只包含必要的计划收尾或测试修正：

```text
test: verify image math boundary invariants
```

## Acceptance

- `backend/app/image_math/` 存在，并只输出底层数学数据、bytes 或 metrics。
- `backend/app/json_tools.py` 存在，并统一封装 orjson。
- Pillow、NumPy、scikit-image 只在 `backend/app/image_math/` 直接导入。
- `orjson` 只在 `backend/app/json_tools.py` 直接导入。
- `rich` 不出现在 `backend/app/`。
- image_math 不导入 M29 domain modules、upload pipeline、plan materializer、Renderer 或 DSL schema。
- image_math 文件中不出现 `pixelOwner`、`replayDecision`、`cleanupAuthorization`、`materialize`、`autoLayout`、`componentIdentity` 等领域决策合同词。
- 当前 DSL 输出不变。
- 当前 M29.5 replay plan 语义不变。
- 当前 materializer 行为不变。
- 当前 cleanup 行为不变。

## Validation

Targeted:

```bash
cd backend
uv run pytest tests/test_json_tools.py -q
uv run pytest tests/test_image_math_arrays.py tests/test_image_math_masks.py tests/test_image_math_components.py tests/test_image_math_alpha.py -q
uv run pytest tests/test_image_math_import_boundaries.py -q
```

Full backend:

```bash
cd backend
uv run pytest -q
```

Repository hygiene:

```bash
git diff --check
git status --short --branch
```

## Notes

- `docs/reference/codex_prompt.md` and `docs/reference/code_review_first_principles_technical_plan.md` are input evidence for this plan. They are not required as committed product docs unless explicitly requested.
- `/Users/luhui/Downloads/525测试` remains useful for later behavior migration and real sample validation. It is not a closing signal for this first round because no production behavior should consume image_math yet.
- Future stages must add parity tests before replacing existing report-only internals.
