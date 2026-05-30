# 092 Codia Beta Assets And Online Detector

- 状态：completed
- 日期：2026-05-31
- 关联计划：[091 Codia DSL 0.2 Plugin Beta Runtime](091-codia-dsl-02-plugin-beta-runtime.md)

## Goal

补齐 Codia Beta 插件闭环中遗漏的两块一等输入：

```text
PNG
-> OCR
-> M29 physical evidence
-> optional online VLM detector candidates
-> Codia assembly/control/tree
-> DSL v0.2 with local image crop assets
-> renderCodiaRuntimeDesign
-> Figma
```

## Root Cause

091 只把 DSL v0.2 的结构树接进插件，没有把 ImageView 的真实 crop asset 接进去，也没有把 VLM detector 作为每次上传的在线阶段接进 `codiaserver`。

实测失败形态：

```text
runtime DSL assets=0
runtime DSL imageNodes>0
runtime DSL imageNodesWithSource=0
assembly detectorCandidateCount=0
Renderer warning CODIA_RUNTIME_IMAGE_SOURCE_NOT_FOUND
```

## Changes

- `internal/codia/dsl02` 增加 asset-aware export：
  - 遍历最终 `type="image"` 节点。
  - 使用节点 `SourceBBox` 从原始 PNG 裁 crop。
  - 写入 `compile/assets/{assetId}.png`。
  - 写入 DSL `assets[]` 和 `node.image.assetId`。
- `internal/codia/server` 增加：
  - `GET /api/codia-preview/{taskId}/assets/{assetId}.png`
  - `CODIA_SERVER_DETECTOR_ENABLED=true` 在线 detector 阶段。
  - detector 成功后把 `compile/detector/ui_detector_candidates.v1.json` 传入 compiler。
- 插件 Beta Renderer 调用传入：

```text
assetBaseUrl = API_BASE_URL + "/codia-preview/{taskId}"
```

## Validation

已验证：

```text
cd services/backend-go && go test ./internal/codia/dsl02 ./internal/codia/compiler ./internal/codia/server ./cmd/codiaserver
pnpm --filter @image-figma/figma-plugin run typecheck
```

HTTP 闭环验证：

```text
POST /api/codia-preview
GET /api/codia-preview/{taskId}/dsl
GET /api/codia-preview/{taskId}/assets/{assetId}.png
```

验证结果：

```text
assets=38
imageNodes=38
imageNodesWithSource=38
asset endpoint HTTP/1.1 200 OK
asset file: PNG image data
```

在线 detector smoke 验证：

```text
CODIA_SERVER_DETECTOR_ENABLED=true
CODIA_UI_DETECTOR_PASSES=imageview
POST /api/codia-preview
```

验证结果：

```text
detectorCandidates=28
imageView=28
assembly detectorCandidateCount=28
assets=52
imageNodes=52
imageNodesWithSource=52
```

## Remaining Risk

`CODIA_SERVER_DETECTOR_ENABLED=true` 会调用外部 OpenAI-compatible VLM provider，运行质量、速度和成本取决于 `CODIA_UI_DETECTOR_*` 配置。本计划只接入在线 detector 阶段和候选传递合同，不承诺 VLM 输出质量。
