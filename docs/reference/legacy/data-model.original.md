下面输出补充文档：

**`04_技术架构文档/10_数据模型与SQLite表结构_v0.1.md`**

~~~markdown
# 数据模型与 SQLite 表结构 v0.1

文档名称：数据模型与 SQLite 表结构  
所属项目：Image-to-Figma Design  
当前版本：v0.1  
版本性质：MVP 后端数据模型设计文档  
适用阶段：第一版核心链路开发 / 后端开发 / 联调 / 内测  
最后更新：2026-05-16  

---

## 1. 文档目的

本文档用于定义 Image-to-Figma Design v0.1 的后端数据模型与 SQLite 表结构。

v0.1 的核心链路是：

```text
PNG 上传
→ 创建任务
→ 后端识别
→ 生成 DSL v0.1
→ 图片资产保存
→ 插件获取 DSL
→ Figma 渲染
~~~

因此，后端至少需要记录：

```text
任务信息
图片资产信息
DSL 结果信息
错误日志
模型调用日志
```

v0.1 不做复杂数据平台，也不做完整商业化数据模型，但必须保证主链路可追踪、可调试、可迁移。

------

## 2. v0.1 数据模型设计原则

v0.1 数据模型遵循以下原则：

```text
1. 简单够用
2. 围绕 taskId 串联所有数据
3. 文件内容不直接塞数据库，只存路径和元数据
4. 原图、资产、DSL、日志都能追踪
5. 错误能定位到 task / stage / element / asset
6. 预留后续迁移 PostgreSQL / OSS 的字段
7. 不做用户、支付、额度、团队等商业化模型
```

一句话：

> SQLite 可以简单，但 taskId、assetId、dslPath、errorCode 这些关键字段必须清楚。

------

## 3. 为什么 v0.1 使用 SQLite

v0.1 推荐使用 SQLite，原因：

```text
开发快
部署简单
本地调试方便
不需要额外数据库服务
足够支撑 MVP 和小规模内测
```

v0.1 不建议一开始引入复杂数据库架构：

```text
不强制 PostgreSQL
不强制 Redis
不强制分库分表
不强制复杂索引
```

但字段设计要预留后续迁移：

```text
taskId
assetId
storageType
objectKey
dslPath
createdAt
updatedAt
```

后续生产阶段可以升级：

```text
SQLite → PostgreSQL
本地文件 → OSS / 对象存储
本地日志 → 日志服务
JSON 文件 → PostgreSQL JSONB
```

------

## 4. v0.1 推荐数据表

v0.1 推荐 5 张表：

```text
tasks
assets
dsl_results
error_logs
model_call_logs
```

其中：

```text
tasks：任务主表
assets：图片资产表
dsl_results：DSL 结果表
error_logs：错误日志表
model_call_logs：模型调用日志表
```

如果想极简实现，可以先做 4 张：

```text
tasks
assets
dsl_results
error_logs
```

但建议 v0.1 保留 `model_call_logs`，因为后续排查模型效果、prompt 版本、耗时和成本时非常重要。

------

## 5. 表关系总览

```text
tasks
  ├─ assets
  ├─ dsl_results
  ├─ error_logs
  └─ model_call_logs
```

核心关联字段：

```text
taskId
```

每个任务都有一个唯一 `taskId`。

每个 asset、DSL 结果、错误日志、模型调用日志都通过 `taskId` 关联到任务。

------

## 6. 文件存储与数据库关系

v0.1 不建议把原图、裁切图片、DSL JSON 大字段直接存入 SQLite。

推荐：

```text
文件内容存在本地文件系统
数据库只存路径、URL、元数据
```

本地目录建议：

```text
backend/storage/
├─ uploads/
│  └─ {taskId}/
│     └─ original.png
│
├─ assets/
│  └─ {taskId}/
│     ├─ product_001.jpg
│     ├─ banner_001.jpg
│     └─ fallback_001.png
│
├─ dsl/
│  └─ {taskId}/
│     ├─ result.dsl.json
│     ├─ normalized.dsl.json
│     └─ repaired.dsl.json
│
└─ logs/
   └─ {taskId}/
      ├─ pipeline.log
      ├─ model_calls.jsonl
      └─ errors.jsonl
```

数据库中存：

```text
originalImagePath
assetPath
assetUrl
dslPath
logPath
```

------

## 7. tasks 表

### 7.1 表用途

`tasks` 是任务主表。

每次用户上传一张 PNG，就创建一条 task 记录。

该表用于记录：

```text
任务 ID
任务状态
原图信息
处理进度
失败原因
耗时
结果路径
```

------

### 7.2 建表 SQL

```sql
CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,

  task_id TEXT NOT NULL UNIQUE,

  status TEXT NOT NULL,
  stage TEXT,

  progress INTEGER DEFAULT 0,
  message TEXT,

  source TEXT DEFAULT 'figma_plugin',
  client_version TEXT,

  original_file_name TEXT,
  original_format TEXT,
  original_width INTEGER,
  original_height INTEGER,
  normalized_width INTEGER,
  normalized_height INTEGER,
  scale_factor REAL DEFAULT 1,

  file_size INTEGER,
  original_image_path TEXT,
  original_image_url TEXT,

  quality_flags TEXT,

  dsl_result_id INTEGER,
  dsl_path TEXT,

  error_code TEXT,
  error_message TEXT,

  duration_ms INTEGER,

  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  completed_at TEXT,
  failed_at TEXT
);
```

------

### 7.3 字段说明

| 字段                  | 类型    | 必填 | 说明                      |
| --------------------- | ------- | ---- | ------------------------- |
| `id`                  | integer | 是   | 自增主键                  |
| `task_id`             | text    | 是   | 对外任务 ID，唯一         |
| `status`              | text    | 是   | 任务状态                  |
| `stage`               | text    | 否   | 当前处理阶段              |
| `progress`            | integer | 否   | 进度 0～100               |
| `message`             | text    | 否   | 插件端可显示的简单文案    |
| `source`              | text    | 否   | 来源，默认 `figma_plugin` |
| `client_version`      | text    | 否   | 插件版本                  |
| `original_file_name`  | text    | 否   | 原始文件名                |
| `original_format`     | text    | 否   | 图片格式，v0.1 通常为 png |
| `original_width`      | integer | 否   | 原始图片宽度              |
| `original_height`     | integer | 否   | 原始图片高度              |
| `normalized_width`    | integer | 否   | Figma 坐标宽度            |
| `normalized_height`   | integer | 否   | Figma 坐标高度            |
| `scale_factor`        | real    | 否   | 原图到 Figma 坐标缩放比例 |
| `file_size`           | integer | 否   | 文件大小，单位 byte       |
| `original_image_path` | text    | 否   | 原图本地路径              |
| `original_image_url`  | text    | 否   | 原图访问 URL              |
| `quality_flags`       | text    | 否   | JSON 字符串，记录质量风险 |
| `dsl_result_id`       | integer | 否   | 关联 dsl_results.id       |
| `dsl_path`            | text    | 否   | 最终 DSL 文件路径         |
| `error_code`          | text    | 否   | 任务失败错误码            |
| `error_message`       | text    | 否   | 任务失败错误信息          |
| `duration_ms`         | integer | 否   | 总耗时                    |
| `created_at`          | text    | 是   | 创建时间                  |
| `updated_at`          | text    | 是   | 更新时间                  |
| `completed_at`        | text    | 否   | 完成时间                  |
| `failed_at`           | text    | 否   | 失败时间                  |

------

### 7.4 status 枚举

v0.1 支持：

```text
pending
uploaded
processing
completed
failed
```

说明：

| 状态         | 说明                 |
| ------------ | -------------------- |
| `pending`    | 任务已创建，等待处理 |
| `uploaded`   | 原图已上传           |
| `processing` | 处理中               |
| `completed`  | 处理完成，DSL 已生成 |
| `failed`     | 任务失败             |

------

### 7.5 stage 枚举

v0.1 内部阶段：

```text
upload
preprocess
ocr
ai_analyze
asset_crop
dsl_build
dsl_validate
dsl_repair
completed
failed
```

`stage` 用于开发调试，不一定展示给普通用户。

------

### 7.6 quality_flags 存储格式

SQLite 中用 TEXT 存 JSON 字符串。

示例：

```json
["blurred", "low_contrast_text", "long_screenshot"]
```

常见值：

```text
low_resolution
blurred
too_large
too_small
long_screenshot
low_contrast_text
many_fallback_regions
```

------

## 8. assets 表

### 8.1 表用途

`assets` 用于记录任务生成过程中产生的图片资产。

包括：

```text
原图
头像
商品图
Banner
Logo
fallback 区域
图标 fallback 图片
```

------

### 8.2 建表 SQL

```sql
CREATE TABLE IF NOT EXISTS assets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,

  asset_id TEXT NOT NULL UNIQUE,
  task_id TEXT NOT NULL,

  type TEXT NOT NULL DEFAULT 'image',
  role TEXT,

  file_name TEXT,
  format TEXT,
  width INTEGER,
  height INTEGER,
  file_size INTEGER,

  local_path TEXT,
  url TEXT,

  storage_type TEXT DEFAULT 'local',
  object_key TEXT,
  expires_at TEXT,

  source_bbox TEXT,
  crop_padding INTEGER,
  is_fallback INTEGER DEFAULT 0,
  fallback_reason TEXT,

  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

------

### 8.3 字段说明

| 字段              | 类型    | 必填 | 说明                          |
| ----------------- | ------- | ---- | ----------------------------- |
| `id`              | integer | 是   | 自增主键                      |
| `asset_id`        | text    | 是   | 资源 ID，唯一                 |
| `task_id`         | text    | 是   | 所属任务 ID                   |
| `type`            | text    | 是   | 资源类型，v0.1 主要为 `image` |
| `role`            | text    | 否   | 资源角色                      |
| `file_name`       | text    | 否   | 文件名                        |
| `format`          | text    | 否   | png / jpeg / jpg / webp       |
| `width`           | integer | 否   | 图片宽度                      |
| `height`          | integer | 否   | 图片高度                      |
| `file_size`       | integer | 否   | 文件大小                      |
| `local_path`      | text    | 否   | 本地文件路径                  |
| `url`             | text    | 否   | 插件可访问 URL                |
| `storage_type`    | text    | 否   | local / oss                   |
| `object_key`      | text    | 否   | OSS 对象路径                  |
| `expires_at`      | text    | 否   | 签名 URL 过期时间             |
| `source_bbox`     | text    | 否   | 原图 bbox，JSON 字符串        |
| `crop_padding`    | integer | 否   | 裁切外扩像素                  |
| `is_fallback`     | integer | 否   | 是否 fallback 资源，0 / 1     |
| `fallback_reason` | text    | 否   | fallback 原因                 |
| `created_at`      | text    | 是   | 创建时间                      |
| `updated_at`      | text    | 是   | 更新时间                      |

------

### 8.4 role 枚举建议

```text
original
product_image
avatar
banner_image
logo
illustration
icon_fallback
fallback_region
status_bar
background_image
```

------

### 8.5 source_bbox 格式

SQLite 中用 TEXT 存 JSON 数组。

示例：

```json
[32, 240, 748, 520]
```

含义：

```text
[x1, y1, x2, y2]
```

这里是原始 PNG 坐标，不是 Figma 坐标。

------

### 8.6 assets 表与 DSL assets 的关系

数据库 assets 表记录：

```text
asset_id
url
format
width
height
storage_type
object_key
```

DSL 中对应：

```json
{
  "assetId": "asset_product_001",
  "type": "image",
  "role": "product_image",
  "url": "http://localhost:8000/files/assets/task_001/product_001.jpg",
  "format": "jpeg",
  "width": 96,
  "height": 96,
  "storage": "local"
}
```

------

## 9. dsl_results 表

### 9.1 表用途

`dsl_results` 用于记录每个任务生成的 DSL 结果。

v0.1 建议不直接把完整 DSL JSON 存入数据库，而是存文件路径。

------

### 9.2 建表 SQL

```sql
CREATE TABLE IF NOT EXISTS dsl_results (
  id INTEGER PRIMARY KEY AUTOINCREMENT,

  dsl_id TEXT NOT NULL UNIQUE,
  task_id TEXT NOT NULL,

  version TEXT NOT NULL DEFAULT '0.1',

  dsl_path TEXT NOT NULL,
  normalized_dsl_path TEXT,
  repaired_dsl_path TEXT,

  element_count INTEGER DEFAULT 0,
  asset_count INTEGER DEFAULT 0,
  fallback_count INTEGER DEFAULT 0,

  validation_status TEXT,
  validation_errors TEXT,
  validation_warnings TEXT,

  prompt_version TEXT,
  model TEXT,

  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

------

### 9.3 字段说明

| 字段                  | 类型    | 必填 | 说明                      |
| --------------------- | ------- | ---- | ------------------------- |
| `id`                  | integer | 是   | 自增主键                  |
| `dsl_id`              | text    | 是   | DSL 结果 ID，唯一         |
| `task_id`             | text    | 是   | 所属任务 ID               |
| `version`             | text    | 是   | DSL 版本，v0.1 固定为 0.1 |
| `dsl_path`            | text    | 是   | 原始 DSL 文件路径         |
| `normalized_dsl_path` | text    | 否   | normalize 后 DSL 文件路径 |
| `repaired_dsl_path`   | text    | 否   | repair 后 DSL 文件路径    |
| `element_count`       | integer | 否   | 元素数量                  |
| `asset_count`         | integer | 否   | 资产数量                  |
| `fallback_count`      | integer | 否   | fallback 数量             |
| `validation_status`   | text    | 否   | passed / failed           |
| `validation_errors`   | text    | 否   | JSON 字符串               |
| `validation_warnings` | text    | 否   | JSON 字符串               |
| `prompt_version`      | text    | 否   | 主分析 prompt 版本        |
| `model`               | text    | 否   | 主模型名称                |
| `created_at`          | text    | 是   | 创建时间                  |
| `updated_at`          | text    | 是   | 更新时间                  |

------

### 9.4 validation_status 枚举

```text
passed
failed
warning
```

说明：

| 状态      | 说明               |
| --------- | ------------------ |
| `passed`  | DSL 校验通过       |
| `failed`  | DSL 校验失败       |
| `warning` | 通过但存在 warning |

------

### 9.5 validation_errors 格式

SQLite 中用 TEXT 存 JSON。

示例：

```json
[
  {
    "code": "TEXT_CONTENT_MISSING",
    "message": "Text element content.text is missing",
    "path": "root.children[3]",
    "elementId": "txt_003"
  }
]
```

------

### 9.6 为什么不直接存完整 DSL

v0.1 不建议把完整 DSL 塞入 SQLite，原因：

```text
DSL 可能很大
文件更方便人工查看
文件更方便给 Renderer 测试
文件更方便版本对比
后续迁移对象存储更自然
```

数据库只存：

```text
dsl_path
element_count
asset_count
fallback_count
validation_status
```

如果后续迁移 PostgreSQL，可以考虑用 JSONB 存 DSL 摘要或完整 DSL。

------

## 10. error_logs 表

### 10.1 表用途

`error_logs` 用于记录任务失败、局部错误、资产错误、DSL 错误、Renderer 错误等。

所有错误都应尽量关联：

```text
taskId
stage
errorCode
```

如果能定位到具体元素或资源，则记录：

```text
elementId
assetId
```

------

### 10.2 建表 SQL

```sql
CREATE TABLE IF NOT EXISTS error_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,

  error_id TEXT NOT NULL UNIQUE,
  task_id TEXT,

  stage TEXT,
  error_code TEXT NOT NULL,
  error_message TEXT NOT NULL,
  error_detail TEXT,

  severity TEXT DEFAULT 'medium',

  element_id TEXT,
  asset_id TEXT,

  stack_trace TEXT,
  context TEXT,

  created_at TEXT NOT NULL
);
```

------

### 10.3 字段说明

| 字段            | 类型    | 必填 | 说明                |
| --------------- | ------- | ---- | ------------------- |
| `id`            | integer | 是   | 自增主键            |
| `error_id`      | text    | 是   | 错误 ID，唯一       |
| `task_id`       | text    | 否   | 关联任务 ID         |
| `stage`         | text    | 否   | 出错阶段            |
| `error_code`    | text    | 是   | 错误码              |
| `error_message` | text    | 是   | 错误说明            |
| `error_detail`  | text    | 否   | 详细信息            |
| `severity`      | text    | 否   | 严重程度            |
| `element_id`    | text    | 否   | 关联 DSL elementId  |
| `asset_id`      | text    | 否   | 关联 assetId        |
| `stack_trace`   | text    | 否   | 堆栈信息            |
| `context`       | text    | 否   | JSON 字符串，上下文 |
| `created_at`    | text    | 是   | 创建时间            |

------

### 10.4 severity 枚举

```text
low
medium
high
fatal
```

说明：

| 等级     | 说明                  |
| -------- | --------------------- |
| `low`    | 轻微问题，不影响生成  |
| `medium` | 局部问题，可 fallback |
| `high`   | 影响关键内容          |
| `fatal`  | 导致任务失败          |

------

### 10.5 stage 枚举

```text
upload
preprocess
ocr
ai_analyze
asset_crop
dsl_build
dsl_validate
dsl_repair
asset
figma_render
unknown
```

------

### 10.6 error_code 建议

上传类：

```text
UPLOAD_FAILED
INVALID_IMAGE_FORMAT
IMAGE_TOO_LARGE
IMAGE_READ_FAILED
```

处理类：

```text
PREPROCESS_FAILED
OCR_FAILED
AI_ANALYZE_FAILED
MODEL_JSON_PARSE_FAILED
DSL_BUILD_FAILED
DSL_SCHEMA_ERROR
DSL_REPAIR_FAILED
```

资产类：

```text
ASSET_CROP_FAILED
ASSET_NOT_FOUND
ASSET_URL_EXPIRED
ASSET_LOAD_FAILED
```

Renderer 类：

```text
UNSUPPORTED_DSL_VERSION
INVALID_ELEMENT_TYPE
INVALID_LAYOUT
TEXT_CONTENT_MISSING
ICON_NOT_FOUND
FONT_LOAD_FAILED
FIGMA_RENDER_FAILED
```

通用类：

```text
UNKNOWN_ERROR
INTERNAL_SERVER_ERROR
TASK_TIMEOUT
```

------

### 10.7 context 格式示例

```json
{
  "path": "root.children[4]",
  "bbox": [24, 88, 200, 112],
  "expected": "assetId exists in assets",
  "actual": "asset_product_003 missing"
}
```

------

## 11. model_call_logs 表

### 11.1 表用途

`model_call_logs` 用于记录每次 AI 模型调用。

v0.1 建议保留该表，原因：

```text
方便排查模型输出问题
方便追踪 prompt 版本
方便比较耗时
方便后续成本优化
方便复现失败任务
```

------

### 11.2 建表 SQL

```sql
CREATE TABLE IF NOT EXISTS model_call_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,

  call_id TEXT NOT NULL UNIQUE,
  task_id TEXT NOT NULL,

  stage TEXT NOT NULL,

  model TEXT,
  model_version TEXT,
  prompt_name TEXT,
  prompt_version TEXT,

  input_summary TEXT,
  output_summary TEXT,

  input_tokens INTEGER,
  output_tokens INTEGER,
  estimated_cost REAL,

  duration_ms INTEGER,

  status TEXT NOT NULL,
  error_code TEXT,
  error_message TEXT,

  created_at TEXT NOT NULL
);
```

------

### 11.3 字段说明

| 字段             | 类型    | 必填 | 说明                  |
| ---------------- | ------- | ---- | --------------------- |
| `id`             | integer | 是   | 自增主键              |
| `call_id`        | text    | 是   | 模型调用 ID，唯一     |
| `task_id`        | text    | 是   | 关联任务 ID           |
| `stage`          | text    | 是   | 调用阶段              |
| `model`          | text    | 否   | 模型名称              |
| `model_version`  | text    | 否   | 模型版本              |
| `prompt_name`    | text    | 否   | prompt 名称           |
| `prompt_version` | text    | 否   | prompt 版本           |
| `input_summary`  | text    | 否   | 输入摘要，JSON 字符串 |
| `output_summary` | text    | 否   | 输出摘要，JSON 字符串 |
| `input_tokens`   | integer | 否   | 输入 token            |
| `output_tokens`  | integer | 否   | 输出 token            |
| `estimated_cost` | real    | 否   | 预估成本              |
| `duration_ms`    | integer | 否   | 调用耗时              |
| `status`         | text    | 是   | success / failed      |
| `error_code`     | text    | 否   | 错误码                |
| `error_message`  | text    | 否   | 错误信息              |
| `created_at`     | text    | 是   | 创建时间              |

------

### 11.4 stage 枚举

```text
semantic_analyzer
text_corrector
icon_matcher
dsl_repair
json_repair
quality_review
```

v0.1 主要用：

```text
semantic_analyzer
json_repair
dsl_repair
```

------

### 11.5 status 枚举

```text
success
failed
```

------

### 11.6 input_summary 示例

```json
{
  "imageSize": "390x844",
  "ocrBlocks": 42,
  "detectedRegions": 18
}
```

------

### 11.7 output_summary 示例

```json
{
  "components": 12,
  "textBlocks": 38,
  "fallbackRegions": 3,
  "lowConfidenceItems": 5
}
```

------

### 11.8 是否保存完整模型输入输出

v0.1 开发阶段可以保存完整模型输入输出到文件：

```text
backend/storage/logs/{taskId}/model_calls.jsonl
```

数据库只保存摘要。

原因：

```text
数据库保持轻量
文件方便调试
后续可做脱敏和清理
```

商业化前需要重新制定隐私策略。

------

## 12. 可选表：render_logs

### 12.1 是否 v0.1 必须

`render_logs` 不是 v0.1 必须表。

Renderer 大部分运行在 Figma 插件端，v0.1 可以先通过插件 console 或开发版调试信息查看。

如果后续插件把渲染结果回传后端，可以增加：

```text
render_logs
```

------

### 12.2 可选建表 SQL

```sql
CREATE TABLE IF NOT EXISTS render_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,

  render_id TEXT NOT NULL UNIQUE,
  task_id TEXT NOT NULL,

  root_node_id TEXT,
  rendered_element_count INTEGER,
  skipped_element_count INTEGER,
  warning_count INTEGER,

  warnings TEXT,

  status TEXT NOT NULL,
  error_code TEXT,
  error_message TEXT,

  duration_ms INTEGER,

  created_at TEXT NOT NULL
);
```

------

### 12.3 v0.1 建议

v0.1 可以暂不建该表。

如果要做开发版插件调试增强，再加。

------

## 13. 索引设计

SQLite v0.1 建议加基础索引。

```sql
CREATE INDEX IF NOT EXISTS idx_tasks_task_id
ON tasks(task_id);

CREATE INDEX IF NOT EXISTS idx_tasks_status
ON tasks(status);

CREATE INDEX IF NOT EXISTS idx_assets_task_id
ON assets(task_id);

CREATE INDEX IF NOT EXISTS idx_assets_asset_id
ON assets(asset_id);

CREATE INDEX IF NOT EXISTS idx_dsl_results_task_id
ON dsl_results(task_id);

CREATE INDEX IF NOT EXISTS idx_error_logs_task_id
ON error_logs(task_id);

CREATE INDEX IF NOT EXISTS idx_error_logs_error_code
ON error_logs(error_code);

CREATE INDEX IF NOT EXISTS idx_model_call_logs_task_id
ON model_call_logs(task_id);
```

v0.1 不需要复杂复合索引。

------

## 14. Python ORM 模型建议

如果使用 SQLAlchemy，可以按以下模型拆分：

```text
backend/app/models/
├─ task.py
├─ asset.py
├─ dsl_result.py
├─ error_log.py
└─ model_call_log.py
```

------

## 15. Task ORM 示例

```python
from sqlalchemy import Column, Integer, String, Text, Real

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)

    task_id = Column(String, unique=True, nullable=False)

    status = Column(String, nullable=False)
    stage = Column(String, nullable=True)

    progress = Column(Integer, default=0)
    message = Column(String, nullable=True)

    source = Column(String, default="figma_plugin")
    client_version = Column(String, nullable=True)

    original_file_name = Column(String, nullable=True)
    original_format = Column(String, nullable=True)
    original_width = Column(Integer, nullable=True)
    original_height = Column(Integer, nullable=True)
    normalized_width = Column(Integer, nullable=True)
    normalized_height = Column(Integer, nullable=True)
    scale_factor = Column(Real, default=1)

    file_size = Column(Integer, nullable=True)
    original_image_path = Column(Text, nullable=True)
    original_image_url = Column(Text, nullable=True)

    quality_flags = Column(Text, nullable=True)

    dsl_result_id = Column(Integer, nullable=True)
    dsl_path = Column(Text, nullable=True)

    error_code = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)

    duration_ms = Column(Integer, nullable=True)

    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)
    completed_at = Column(String, nullable=True)
    failed_at = Column(String, nullable=True)
```

------

## 16. Asset ORM 示例

```python
from sqlalchemy import Column, Integer, String, Text

class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, autoincrement=True)

    asset_id = Column(String, unique=True, nullable=False)
    task_id = Column(String, nullable=False)

    type = Column(String, default="image", nullable=False)
    role = Column(String, nullable=True)

    file_name = Column(String, nullable=True)
    format = Column(String, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    file_size = Column(Integer, nullable=True)

    local_path = Column(Text, nullable=True)
    url = Column(Text, nullable=True)

    storage_type = Column(String, default="local")
    object_key = Column(Text, nullable=True)
    expires_at = Column(String, nullable=True)

    source_bbox = Column(Text, nullable=True)
    crop_padding = Column(Integer, nullable=True)
    is_fallback = Column(Integer, default=0)
    fallback_reason = Column(Text, nullable=True)

    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)
```

------

## 17. 数据写入流程

### 17.1 上传阶段

```text
POST /api/upload
↓
生成 taskId
↓
保存原始 PNG 到 storage/uploads/{taskId}/original.png
↓
写入 tasks 表
↓
status = uploaded / processing
```

写入字段：

```text
task_id
status
stage
original_file_name
original_format
original_width
original_height
file_size
original_image_path
created_at
updated_at
```

------

### 17.2 预处理阶段

更新 tasks：

```text
stage = preprocess
normalized_width
normalized_height
scale_factor
quality_flags
```

------

### 17.3 OCR / AI 阶段

更新 tasks：

```text
stage = ocr
stage = ai_analyze
progress
message
```

写入 model_call_logs：

```text
call_id
task_id
stage
model
prompt_version
duration_ms
status
input_summary
output_summary
```

------

### 17.4 图片裁切阶段

写入 assets：

```text
asset_id
task_id
role
format
width
height
local_path
url
source_bbox
is_fallback
fallback_reason
```

------

### 17.5 DSL 生成阶段

保存文件：

```text
backend/storage/dsl/{taskId}/result.dsl.json
```

写入 dsl_results：

```text
dsl_id
task_id
version
dsl_path
element_count
asset_count
fallback_count
validation_status
```

更新 tasks：

```text
dsl_result_id
dsl_path
```

------

### 17.6 完成阶段

更新 tasks：

```text
status = completed
stage = completed
progress = 100
message = 生成完成
duration_ms
completed_at
updated_at
```

------

### 17.7 失败阶段

写入 error_logs。

更新 tasks：

```text
status = failed
stage = failed
progress = 100
error_code
error_message
failed_at
updated_at
```

------

## 18. 任务状态更新规则

任务状态只允许按以下方向流转：

```text
pending
→ uploaded
→ processing
→ completed
```

失败可以发生在任意阶段：

```text
pending / uploaded / processing
→ failed
```

不建议出现：

```text
completed → processing
failed → processing
```

如果需要重试，应创建新 taskId，或增加 retryTaskId 关系，v0.1 可先不做。

------

## 19. 文件路径命名规则

### 19.1 taskId

建议格式：

```text
task_yyyyMMdd_HHmmss_xxxxxx
```

示例：

```text
task_20260516_153012_a8f31c
```

### 19.2 assetId

建议格式：

```text
asset_{role}_{index}
```

示例：

```text
asset_product_001
asset_banner_001
asset_fallback_001
asset_original
```

### 19.3 dslId

建议格式：

```text
dsl_{taskId}
```

示例：

```text
dsl_task_20260516_153012_a8f31c
```

------

## 20. 本地 URL 生成规则

开发阶段：

```text
local_path:
backend/storage/assets/{taskId}/product_001.jpg

url:
http://localhost:8000/files/assets/{taskId}/product_001.jpg
```

原图：

```text
local_path:
backend/storage/uploads/{taskId}/original.png

url:
http://localhost:8000/files/uploads/{taskId}/original.png
```

DSL：

```text
local_path:
backend/storage/dsl/{taskId}/result.dsl.json

url:
http://localhost:8000/api/tasks/{taskId}/dsl
```

------

## 21. 数据库与 DSL 的映射

### 21.1 tasks → DSL 顶层

tasks 表字段映射：

```text
task_id → DSL.taskId
normalized_width → DSL.page.width
normalized_height → DSL.page.height
original_width → DSL.page.originalWidth
original_height → DSL.page.originalHeight
scale_factor → DSL.page.scaleFactor
quality_flags → DSL.meta.qualityFlags
```

------

### 21.2 assets → DSL assets

assets 表字段映射：

```text
asset_id → asset.assetId
type → asset.type
role → asset.role
url → asset.url
format → asset.format
width → asset.width
height → asset.height
storage_type → asset.storage
object_key → asset.objectKey
expires_at → asset.expiresAt
```

------

### 21.3 dsl_results → DSL meta

dsl_results 表字段映射：

```text
version → DSL.version
element_count → DSL.meta.elementCount
fallback_count → DSL.meta.fallbackCount
prompt_version → DSL.meta.promptVersion
model → DSL.meta.model
```

------

## 22. 是否需要存用户信息

v0.1 不需要用户表。

不建：

```text
users
teams
members
roles
permissions
subscriptions
payments
```

如果内测需要简单鉴权，可以使用：

```text
环境变量 token
简单 API key
请求头 Authorization
```

但不作为 v0.1 数据模型核心。

------

## 23. 是否需要存历史记录

v0.1 不做用户侧历史记录。

但 tasks 表天然会保留任务记录，因此内部可以查历史任务。

不需要额外建：

```text
history
recent_tasks
projects
pages
```

后续如果做多页面项目，再新增：

```text
projects
project_pages
```

------

## 24. 是否需要存评分结果

v0.1 不强制评分系统。

不建议现在建复杂表：

```text
quality_scores
visual_diff_results
human_reviews
```

后续 v0.3 做质量评估时再加。

如果想预留，可以在 tasks 表或 dsl_results 表保留：

```text
quality_flags
fallback_count
element_count
```

------

## 25. 是否需要存缓存

v0.1 不做复杂缓存。

不建：

```text
ocr_cache
ai_cache
dsl_cache
image_hash_cache
```

原因：

```text
正常用户不会频繁反复生成同一张图
缓存会增加开发复杂度
```

后续成本优化阶段再考虑。

------

## 26. 数据清理策略

v0.1 开发阶段可以不做自动清理。

但建议预留脚本：

```text
scripts/clean-storage.sh
```

清理内容：

```text
超过 N 天的 uploads
超过 N 天的 assets
超过 N 天的 dsl
超过 N 天的 logs
```

商业化前再设计：

```text
默认保留 30 天
用户手动删除
任务完成后自动清理临时文件
```

------

## 27. SQLite 文件位置

建议：

```text
backend/storage/app.sqlite3
```

或：

```text
backend/data/app.sqlite3
```

推荐：

```text
backend/storage/app.sqlite3
```

因为 v0.1 所有本地数据都在 storage 下。

------

## 28. 数据库初始化脚本

建议文件：

```text
backend/app/database.py
backend/scripts/init_db.py
```

初始化内容：

```text
创建表
创建索引
插入初始配置，可选
```

------

## 29. database.py 建议职责

```text
创建 SQLite engine
创建 session
初始化 Base
提供 get_db
```

示例：

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite:///backend/storage/app.sqlite3"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

------

## 30. v0.1 不需要复杂迁移系统

v0.1 可以先不用 Alembic。

可以通过：

```text
init_db.py
```

直接创建表。

但如果开发团队熟悉 Alembic，也可以引入。

建议：

```text
MVP 早期：init_db.py 足够
内测稳定：再引入 Alembic
```

------

## 31. 后续迁移 PostgreSQL 的预留

v0.1 字段设计要支持后续迁移。

SQLite 当前：

```text
quality_flags TEXT
validation_errors TEXT
context TEXT
input_summary TEXT
output_summary TEXT
```

PostgreSQL 后续可改为：

```text
quality_flags JSONB
validation_errors JSONB
context JSONB
input_summary JSONB
output_summary JSONB
```

本地路径字段后续可切换：

```text
local_path → object_key
url → signed_url
storage_type = oss
```

------

## 32. 数据模型验收标准

v0.1 数据模型完成标准：

```text
1. SQLite 可以初始化成功
2. tasks 表可创建任务
3. assets 表可记录图片资产
4. dsl_results 表可记录 DSL 文件
5. error_logs 表可记录错误
6. model_call_logs 表可记录模型调用摘要
7. taskId 能串联所有数据
8. 插件通过 API 能查询任务和 DSL
9. 后端失败时能写入 error_logs
10. 文件路径和 URL 能正确保存
```

------

## 33. v0.1 明确不做的数据模型

v0.1 不建以下表：

```text
users
teams
members
roles
permissions
subscriptions
payments
usage_records
projects
project_pages
history
quality_scores
visual_diff_results
human_reviews
ocr_cache
ai_cache
dsl_cache
webhooks
api_keys
```

这些全部后续版本再设计。

------

## 34. 推荐最小实现顺序

```text
1. database.py
2. Task model
3. Asset model
4. DslResult model
5. ErrorLog model
6. ModelCallLog model
7. init_db.py
8. task_service.py
9. asset_service.py
10. error_service.py
11. model_log_service.py
```

------

## 35. 服务层建议

### 35.1 task_service.py

职责：

```text
create_task
update_task_status
get_task
mark_completed
mark_failed
```

### 35.2 asset_service.py

职责：

```text
create_asset
get_asset
list_assets_by_task
build_asset_url
```

### 35.3 dsl_service.py

职责：

```text
save_dsl_result
get_dsl_result
get_dsl_path
```

### 35.4 error_service.py

职责：

```text
log_error
list_errors_by_task
mark_task_failed
```

### 35.5 model_log_service.py

职责：

```text
log_model_call_start
log_model_call_success
log_model_call_failed
```

------

## 36. 版本结论

v0.1 使用 SQLite 是合理的。

但即使使用 SQLite，也必须明确数据模型，原因是：

```text
taskId 要可追踪
asset 要可回查
DSL 要可定位
错误要可排查
模型调用要可复现
后续要能迁移
```

v0.1 的数据模型不需要复杂，只需要围绕 5 张表：

```text
tasks
assets
dsl_results
error_logs
model_call_logs
```

只要这 5 张表设计清楚，就足够支撑第一版 MVP 开发、联调和内测。

```

```