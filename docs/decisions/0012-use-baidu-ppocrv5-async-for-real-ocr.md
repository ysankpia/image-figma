# ADR 0012: Use Baidu PP-OCRv5 Async API For Real OCR

- 状态：accepted
- 日期：2026-05-16

## Context

M9 已有 `OCRDocument v0.1` 和 DSL patch harness，但默认 OCR 是 fake。M10 需要真实 OCR boxes 进入合同层，同时不能让 OCR 失败破坏 deterministic fallback DSL。

本地测试比较了 RapidOCR、PaddleOCR PP-OCRv5 server、PaddleOCR PP-OCRv5 mobile 和百度 AI Studio PP-OCRv5 异步 API。百度 PP-OCRv5 异步 API 返回 `rec_texts`、`rec_scores`、`rec_boxes`、`rec_polys`，能直接标准化为内部 OCRDocument。

## Decision

M10 采用百度 AI Studio `PP-OCRv5` 异步 API 作为第一个真实 OCR provider：

```text
OCR_PROVIDER=baidu_ppocrv5
```

默认仍保留：

```text
OCR_PROVIDER=fake
```

后端只使用异步 jobs API，不接同步接口。远端返回必须先转成 `OCRDocument v0.1`，再交给 DSL patch builder。百度输出不能直接成为 DSL 权威。

## Consequences

- 生产镜像不引入本地 PaddleOCR/RapidOCR 重依赖。
- OCR 质量和速度由远端服务承担。
- 需要 `BAIDU_PADDLE_OCR_TOKEN`，且 token 不能进入仓库。
- 百度失败、429、超时或 JSONL 异常只能让 OCR result failed，不能让上传任务失败。
- 可见文字替换仍放到 M11 以后。

## Alternatives Considered

- 本地 PaddleOCR PP-OCRv5 server：质量高，但本地依赖和运行成本重。
- RapidOCR：工程轻，但当前样例上误识别 icon 和符号更多。
- PaddleOCR mobile：速度居中，但噪声更高。
- PaddleOCR-VL-1.5：结构解析能力强，适合后续 layout/primitive 阶段，不作为 M10 OCRDocument 主 provider。
- 同步 OCR API：官方路径不稳定，且不符合当前 task-based 后端形态。
