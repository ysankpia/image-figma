# 091 Codia DSL 0.2 Plugin Beta Runtime

- 状态：completed
- 创建日期：2026-05-30
- 负责人：未指定
- 关联计划：[090 OpenAI-compatible UI Detector Short Pass](090-openai-compatible-ui-detector-short-pass.md)
- 关联质量债：[017 Codia-like Beta UI Role Detector Gap](../../bugs/open/017-codia-like-beta-ui-role-detector-gap.md)

## Goal

新增一条不破坏当前产品主线的 Codia Beta 闭环：

```text
PNG
-> Go codiaserver /api/codia-preview
-> OCR / M29 physical evidence / optional detector candidates
-> Go codiacompile core
-> Codia tree / figma-like artifacts
-> DSL 0.2 Codia Runtime DSL
-> renderCodiaRuntimeDesign
-> Figma
```

关键判断：

```text
旧主线继续使用 DesignDSL v0.1。
Codia-like 路径不硬塞回 DesignDSL v0.1。
DSL 0.2 是 Codia Runtime DSL，只服务 Codia Beta。
```

## Scope

包含：

- 在 `packages/dsl-schema` 增加 DSL 0.2 Codia Runtime 类型和验证器。
- 在 `packages/image-to-figma-renderer` 增加 `renderCodiaRuntimeDesign`。
- 在 `services/backend-go` 增加 DSL 0.2 exporter。
- 让 Go `cmd/codiacompile` 直接写出 `codia_runtime.dsl.v0_2.json`。
- 在 `services/backend-go` 增加 `cmd/codiaserver`，提供 Codia Beta 专用 HTTP API。
- 在插件新增 `Generate Beta` 路径，调用 Go server 并渲染 DSL 0.2。
- 更新架构、Renderer 和测试文档，记录 DSL 0.2 边界。

不包含：

- 不替换 `/api/upload-preview`。
- 不改变 `/api/tasks/{taskId}/dsl` 的 v0.1 含义。
- 不在本轮新增 Python FastAPI `codia-preview` route。
- 不恢复 M29 Direct、legacy M30、M31-M39/M39.1 runtime 或 ONNX proposer。
- 不让 VLM detector 成为 Beta 路径必需条件。
- 不承诺 Codia/Figma canvas JSON byte-for-byte 一致。
- 不把 golden Codia JSON、样本名、固定坐标、品牌文案或固定 bbox 写入 generation。

## Contracts

### DSL 0.2

顶层：

```text
version = "0.2"
kind = "codia_runtime"
taskId
page
assets
root
meta
```

节点保留 Codia 可见语义：

```text
Root / Groups / Button / Text / Image / Background
ViewGroup / ListView / BottomNavigation / ActionBar / StatusBar
ImageView / TextView / EditText / bg_Button / bg_EditText
```

渲染类型只允许：

```text
frame / group / text / shape / image
```

所有 bbox 为父级局部坐标，`meta.sourceBBox` 可保留源图绝对坐标。Renderer 不做 ownership 或 role 仲裁。

### Go Backend Artifact

```text
services/backend-go/cmd/codiacompile
-> codia_runtime.dsl.v0_2.json
```

`codiacompile` 已经拥有 OCR 输入、M29 physical evidence、assembly、control、tree、figma-like tree 和 canvas export。DSL 0.2 exporter 必须挂在这个 Go artifact 末端，不能绕回 Python 重新仲裁 role/ownership。

### Plugin

默认按钮：

```text
Generate from PNG -> /api/upload-preview -> DesignDSL v0.1 -> renderDesign
```

Beta 按钮：

```text
Generate Beta
-> POST /api/codia-preview
-> GET /api/codia-preview/{taskId}
-> GET /api/codia-preview/{taskId}/dsl
-> Codia Runtime DSL v0.2
-> renderCodiaRuntimeDesign
```

Beta path 由 `services/backend-go/cmd/codiaserver` 提供 HTTP API。插件仍使用同一个 `API_BASE_URL` 默认值 `http://localhost:8000/api`，所以本地测试时 Python FastAPI 和 Go `codiaserver` 不能同时占用 8000 端口。

## Steps

1. 增加 DSL 0.2 类型、验证器和单元测试。
2. 增加 Codia Runtime renderer 和 fake-adapter 测试。
3. 增加 Go `internal/codia/dsl02` exporter 和测试。
4. 接入 `cmd/codiacompile` artifact 输出。
5. 同步文档和验证策略。
6. 跑 DSL、Renderer、Go Codia tests 和 smoke。
7. 增加 Go `codiaserver` HTTP wrapper，暴露 `/api/codia-preview`。
8. 插件新增 Beta 按钮，走 DSL 0.2 renderer。

## Acceptance

- 现有 DSL v0.1 `validateDSL` 仍只接受 `"0.1"`。
- DSL 0.2 validator 能接受合法 Codia Runtime DSL，并拒绝缺失 version/kind/page/root/bbox/text content/image asset 的输入。
- `renderCodiaRuntimeDesign` 能渲染 frame/group/text/shape/image，图片缺失时产生 warning 而不中断。
- Go `codiacompile` 能输出 `codia_runtime.dsl.v0_2.json`。
- Go Codia 四图 smoke 仍可运行，当前 Go compiler ownership/tree artifacts 不被 DSL 0.2 适配层污染。
- Python FastAPI `/api/upload-preview` 和插件默认 v0.1 上传路径不变。
- Go `codiaserver` 能接受 PNG，后台运行 Go Codia compiler，并通过 `/api/codia-preview/{taskId}/dsl` 返回 DSL 0.2。
- 插件 `Generate Beta` 能上传 PNG、轮询 Go Codia task、获取 DSL 0.2，并调用 `renderCodiaRuntimeDesign` 写入 Figma。

## Validation

```bash
pnpm --filter @image-figma/dsl-schema run typecheck
pnpm --filter @image-figma/dsl-schema run test
pnpm --filter @image-figma/image-to-figma-renderer run typecheck
pnpm --filter @image-figma/image-to-figma-renderer run test
cd services/backend-go && go test ./internal/codia/... ./cmd/codiacompile ./cmd/codiaanalyze
cd services/backend-go && go test ./internal/codia/server ./cmd/codiaserver
pnpm --filter @image-figma/figma-plugin run typecheck
pnpm --filter @image-figma/figma-plugin run build
bash services/backend-go/tools/codia_smoke_4img.sh
git diff --check
git status --short --branch
```

已验证：

```text
pnpm --filter @image-figma/dsl-schema run typecheck
pnpm --filter @image-figma/dsl-schema run test
pnpm --filter @image-figma/image-to-figma-renderer run typecheck
pnpm --filter @image-figma/image-to-figma-renderer run test
pnpm --filter @image-figma/figma-plugin run typecheck
pnpm --filter @image-figma/figma-plugin run build
cd services/backend-go && go test ./internal/codia/... ./cmd/codiacompile ./cmd/codiaanalyze ./cmd/codiaserver
bash services/backend-go/tools/codia_smoke_4img.sh
git diff --check
```

Go HTTP 闭环也已用临时端口验证：

```text
codiaserver POST /api/codia-preview
-> GET /api/codia-preview/{taskId}
-> GET /api/codia-preview/{taskId}/dsl
-> version=0.2 kind=codia_runtime stage=codia_completed progress=100
```

## Notes

第一版 DSL 0.2 可以把 Go Codia `Image` 节点渲染为矩形占位，除非后端已经能提供稳定可 fetch 的 crop asset。图片资产补全是后续质量项，不阻塞 Beta 结构闭环。

Detector candidates 继续保持可选输入。没有 detector 时，Beta 路径使用 conservative M29/OCR/Go assembly 输出；有 detector 时，Go compiler 自己决定是否消费。Python/Plugin 不参与 role 仲裁。

当前仓库事实是：Python FastAPI 仍是正式产品 HTTP API，Go 是最新 Codia compiler 内核。Codia Beta 插件路径已经通过 Go `codiaserver` 接入；不要把 Codia Beta 绕回 Python adapter。
