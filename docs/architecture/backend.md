# 后端架构

后端负责接收 PNG、创建任务、生成 DSL、保存资产并提供 API。

## Responsibilities

后端必须支持：

- 健康检查。
- PNG 上传。
- 任务创建。
- 任务状态查询。
- DSL 查询。
- 资产访问。
- 本地存储。
- 错误记录。

## Processing Pipeline

M4 当前管线：

```text
receive multipart PNG
-> validate MIME and PNG signature
-> save original image
-> create development banner asset
-> build fake DSL from mobile-home example
-> save DSL JSON
-> mark task completed
```

后续真实 v0.1 管线：

```text
load original image
-> validate PNG
-> preprocess image
-> run OCR
-> run AI / CV analysis
-> crop assets
-> build DSL
-> normalize DSL
-> validate DSL
-> repair DSL when safe
-> save result
```

## Storage

开发阶段使用本地文件存储：

```text
backend/storage/
  uploads/
  assets/
  dsl/
  logs/
```

M4 服务启动或测试运行时会创建这些目录。`backend/storage/` 不进入 git。

## Task State

M4 当前只实际写入：

- `completed`
- `failed`

后续完整任务状态：

- `pending`
- `uploaded`
- `processing`
- `completed`
- `failed`

任务阶段：

- `upload`
- `task_lookup`
- `dsl_lookup`
- `asset_lookup`
- `preprocess`
- `ocr`
- `ai_analyze`
- `asset_crop`
- `dsl_build`
- `dsl_validate`
- `completed`
- `failed`

## AI Strategy

普通页面：

```text
OCR / CV 预处理
-> 1 次主 AI 结构分析
-> DSL Builder
```

异常 JSON：

```text
最多 1 次 JSON repair
```

不做多轮复杂分析、多模型对比、评分后自动修复。

## Backend Non-Goals

M4 不做：

- 用户系统。
- 支付和额度。
- 批量任务。
- 完整历史记录。
- 复杂队列。
- Redis 缓存。
- 微服务拆分。
- 正式对象存储策略。
- OCR。
- AI。
- 真实裁切。
