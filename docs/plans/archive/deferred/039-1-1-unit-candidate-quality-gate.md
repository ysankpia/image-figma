# M39.1.1 Unit Candidate Quality Gate

- 状态：deferred
- 创建日期：2026-05-22
- 暂缓原因：M29 backend downstream pruning 已从当前 runtime 删除 M39.1 unit structure readiness audit；本计划只保留为历史候选，不能作为当前 active work 执行。
- 负责人：未指定

## Goal

M39.1.1 把 M39.1 的 `candidateUnits[]` 从“候选枚举”升级为“可审计质量分层”。它不做 promotion，不改 DSL，不改资产，不创建 Figma 节点，只回答：

```text
哪些 unit 候选足够可信，后续可以进入 M39.2 promotion？
哪些只是 icon fragment、micro unit、重复 bbox、content/chrome 混合或模型孤证？
```

## Scope

包含：

- 扩展 M39.1 candidate contract。
- 给每个 candidate 写入：
  ```text
  promotionReady: true | false
  qualityTier: high | medium | low | reject
  qualityReasons: []
  rejectReasons: []
  duplicateOfCandidateId: optional
  ```
- 对 product card、banner、chrome shell、content section 做通用质量门。
- 拒绝小 icon、小图片、重复 bbox、纯模型框、content/chrome 混合候选。
- 只让 `promotionReady=true` 的候选进入 `promotionHints[]`。
- 保持 M39.1 的只读/report-only 性质。

不包含：

- 不做 M39.2 unit promotion。
- 不做 M40 nested hierarchy 或 layout semantics。
- 不创建 Figma Component/Instance。
- 不为黑条、搜索框、轮播图写单点规则。
- 不把 ONNX/UIC/Codia 输出当内部真值源。

## Quality Gates

### Product Card Candidate

必须满足：

- bbox 达到最小尺寸和面积门槛，拒绝 30px、40px 级 icon/image fragment。
- boundary classification 不能混合 `content` 和 `chrome`。
- 至少包含一个 substantial image 或 composite media 证据。
- 至少包含 text/metadata 证据，或与现有 M37 safe unit 有强一致关系。
- 不能与已 safe/promoted unit 高 IoU 重复，除非标为 diagnostic duplicate。

拒绝原因示例：

```text
too_small_for_product_card
image_fragment_only
missing_text_or_metadata
boundary_classification_conflict
duplicate_candidate
overlaps_existing_safe_unit
model_only_untrusted
```

### Banner Candidate

必须满足：

- bbox 宽度占页面宽度比例足够高。
- 面积达到大媒体块门槛。
- 横向长宽比符合 banner/composite media。
- 优先由 `m30_composite_media_asset` 或大 image 证据支撑。

拒绝原因示例：

```text
too_small_for_banner
aspect_ratio_not_banner_like
missing_media_evidence
duplicate_candidate
```

### Chrome Shell Candidate

必须满足：

- 位于顶部或底部 shell 区域，或符合通用浮动 chrome 几何。
- 不能吞入中心内容区 card/banner。
- 不能与 content unit 混合。

拒绝原因示例：

```text
center_content_protected
content_chrome_mixed
insufficient_chrome_coverage
```

### Content Section Candidate

必须满足：

- 聚合多个 content 子节点或多个 card/banner 候选。
- 不跨越 top/bottom chrome shell。
- bbox 不能只是单个小节点的放大外壳。

拒绝原因示例：

```text
single_micro_child_only
content_chrome_mixed
insufficient_child_support
```

## Steps

1. 在 `backend/app/unit_structure_readiness.py` 中扩展 candidate quality fields。
2. 为 product card、banner、chrome shell、content section 增加通用质量判定函数。
3. 增加 candidate dedupe：按 IoU、child id set、bbox 近似重复识别 `duplicateOfCandidateId`。
4. 调整 `promotionHints[]`：只输出 `promotionReady=true` 的候选。
5. 更新 M39.1 report summary，记录 quality tier 计数和 rejected candidate 计数。
6. 补充单元测试和 pipeline 测试。
7. 同步 observability/testing docs。

## Acceptance

- 小 icon、小图片碎片不会再作为 promotion-ready product card。
- `promotionHints[]` 不包含 `qualityTier=reject` 或 `promotionReady=false` 的候选。
- content/chrome 混合候选不会 promotion-ready。
- 模型孤证只能是 diagnostic，不会 promotion-ready。
- 高 IoU 重复候选会被标记 `duplicateOfCandidateId`。
- M39.1 report 仍保持：
  ```text
  dslChanged=false
  createdVisibleNodeCount=0
  assetChanged=false
  ```

## Validation

Focused tests:

```bash
cd backend
uv run pytest tests/test_unit_structure_readiness.py tests/test_m30_upload_pipeline.py -q
```

Full validation:

```bash
cd backend && uv run pytest -q
cd ..
pnpm run check
git diff --check
git status --short --branch
```

## Notes

- M39.1.1 是 M39.2 的前置质量门。
- 如果当前样本仍只有少量 promotion-ready unit，这是正确结果；宁可少升，也不能把碎片升成错误结构。
- 后续 M39.2 只能消费 M39.1.1 通过质量门的候选。
