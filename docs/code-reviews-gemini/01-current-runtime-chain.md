# 01 Current Runtime Chain

## 1. source truth
本层（Upload Preview Orchestration）的 Source Truth 为 **“上传任务的执行编排、环境规整以及生命周期状态”**。它代表了任务的系统级事实（如：任务是否存在、各个子阶段是否成功完成、耗时多久），不直接承载任何视觉算法或物理所有权的推导逻辑。

## 2. input artifacts
* 上传图片的字节流：`storage/uploads/{taskId}.png`
* OCR 原始文本结果：`storage/upload_previews/{taskId}/ocr/document.json`
* 初始及重跑后的 M29 Primitives 信息。

## 3. output artifacts
* 耗时与步骤信息：`storage/upload_previews/{taskId}/stage_timings.json`
* 任务状态记录：系统 SQLite 数据库的任务记录及阶段更新 API。

## 4. code entrypoints
* 核心编排管线：[backend/app/upload_preview/pipeline.py#L38](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/upload_preview/pipeline.py#L38)
* 计时拦截器：[backend/app/upload_preview/timings.py#L37](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/upload_preview/timings.py#L37)
* 批校验脚本：[backend/scripts/run_upload_preview_batch_validation.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/backend/scripts/run_upload_preview_batch_validation.py)

## 5. decision authority
* **拥有判定权**：判定各个处理阶段（`ocr`、`m29`、`m29_2` 到 `materialization`）的先后顺序；判定当 Promotion 发生（即 `sourceOwnershipChanged` 为 `True` 时）重新执行 M29.3/M29.4/M29.5。
* **无权判定**：禁止对具体的物理所有权（pixelOwner）、重放决策（replayDecision）、圆角、颜色或 Cleanup 作出任何业务解释或干预。

## 6. report-only surfaces
* 本层为纯 Orchestration，整个 `timings` 都是 Report-only 指标。

## 7. allowed facts
* 各 Stage 的开始/结束 UTC 时间戳。
* 任务状态更新（"running", "completed", "failed"）。
* 根据配置文件 `settings.upload_preview_profile` 分配生成 debug artifact 的策略。

## 8. forbidden facts
* 禁止对 DSL 输出节点内容作直接补丁修改。
* 禁止在 pipeline 层缓存特定图片的 classification 映射。

## 9. main formulas / gates
* **Promotion 回流拦截门**：
  ```python
  m292_document = promotion_result.m292_document
  if m292_document.get("meta", {}).get("sourceOwnershipChanged"):
      # 重新运行 relation_promoted -> cluster_promoted -> replay_plan_promoted -> ownership_conservation_promoted
  ```

## 10. thresholds and heuristic rationale
* **时效性与超时硬限**：由于 OCR 任务在外部网络环境下可能出现异常抖动，在 `timings.py` 内部使用 `HTTP_MAX_ATTEMPTS = 3` 进行三次指数退避重试，这是出于高并发可靠性做出的数学调优，而非特化规制。

## 11. known information loss
* 经过本层时，如果 Stage 发生非受控崩溃，底层具体报错栈信息会收缩并转化为 `M29_MAINLINE_PIPELINE_FAILED` 写入 Task 状态，丢失了一部分底层 Trace。

## 12. known failure symptoms
* 当 `sourceOwnershipChanged` 发生后，若回流重跑因为关系运算出错，Orchestrator 报错，导致整个任务卡在 fail 状态，前端无法拿到 partial design.dsl。

## 13. tests / guards
* 单元测试：`tests/test_upload_preview_pipeline.py`
* 回归测试：`tests/test_timings_recording.py`

## 14. artifact evidence
* 任务执行后生成在 task 目录下的 `stage_timings.json` 包含了清晰的流水线运行日志：
  ```json
  {
    "stage": "m29_internal_source_promotion",
    "startedAt": "2026-05-26T07:31:01.123Z",
    "elapsedSeconds": 0.082,
    "status": "completed"
  }
  ```

## 15. findings
* **P3 优先级问题** (`docs_or_tests`): `timings.py` 抛出的 `UploadPreviewPipelineError` 会在主捕获处被过滤为 API 报错输出，但局部仍有一些 Exception 未被完全包含，导致在开发环境下难以直接还原 timing 漏记问题。

## 16. recommended next action
* 在批验证脚本中增加 stage 耗时的差异回归记录（Timing regression gate），防止后续新增 `image_math` 计算导致总耗时隐性上涨。
