# 验收标准

验收只看当前 Slice Studio 是否能稳定产出用户确认后的 `assets.zip` 和 `project.zip/design.pen`。

## P0 Must Pass

- ` / ` landing page 可打开。
- `/login` 能登录/注册并设置会话 cookie。
- `/projects` 和 `/projects/:projectId/review` 对匿名用户不可访问。
- `/settings`、`/billing`、`/admin` 路由存在。
- 项目列表按登录用户归属隔离。
- 可以新建项目。
- 可以上传多张页面图片。
- 项目刷新后页面和 slices 仍存在。
- 可以手动画框、选择、移动、缩放、删除、重命名。
- 可以选择 `rect | subject | card` cut mode。
- 自动保存成功，失败时有提示。
- 页面可重命名、替换、删除、拖拽重排。
- `assets.zip` 能导出并包含 originals、slices、manifest、project metadata。
- `project.zip` 能导出并包含 `design.pen`、manifest、project metadata、originals、remainders、visible slices。
- `.pen` visible refs 无绝对路径、无 `../`、无 `source.png`、无 raw/debug/mask refs。
- 导出裁切来自原始 source image，不来自前端 canvas 或 thumbnails。

## P1 Should Pass

- `/api/me` 能返回 entitlement、usage、paymentOrders。
- AI 当前页前检查 entitlement，并记录 usage。
- assets/project 导出前检查 entitlement，并记录 usage。
- `/billing` 能创建 provider-neutral 的 payment order；XPay 配置齐全时返回 checkout URL。
- XPay webhook 验签通过后才能把订单标记为 paid 并发放本地 entitlement；伪造签名不能发放权益。
- AI 当前页能生成普通 rect slices，并保存进现有 slice state。
- AI 全部页能逐页处理，失败页不影响已完成页面。
- AI 结果与已有 slices 高重叠时不会大量重复追加。
- AI batch progress 对长项目可见。
- 大型跨 tile 资产不会稳定切成多个半块。
- OCR 可在有 provider token 时生成 editable text nodes。
- 默认 TypeScript M29 physical evidence 不依赖 Go binary。
- OCR/M29 失败不阻塞 `project.zip` 导出。

## P2 Later

- Slice Studio deployment smoke。
- 更多真实样本自动 artifact inspection。
- AI prompt strategy UI 或可配置 profile。
- `.pen` 视觉截图自动对比。
- 更强的 repeated AI run replace/refresh 机制。

## Real Sample Acceptance

对真实项目至少检查：

- projectCreated=true；
- pageCount 等于上传页数；
- slice save/readback 正常；
- AI batch 完成页数、失败页数、新增/跳过数量可见；
- `assets.zip` 存在且 manifest 与 slice 文件数量一致；
- `project.zip` 存在且 `design.pen` 可打开；
- visible asset refs 全部 package-local；
- OCR/M29 metadata 记录 provider、textLayerCount、fallback/skip reason；
- 刷新页面后项目仍可继续编辑。

## Not Acceptance Items

这些不作为当前验收项：

- Auto Layout。
- Figma Component/Instance。
- 完整 semantic tree。
- 代码生成。
- Codia JSON clone。
- 旧 Draft DSL 通过。
- 旧 Figma plugin render 通过。
- YOLO/M29/OCR/AI 自动 ownership 完全正确。
- 商业化账号、权限、额度、支付。

189 当前阶段已经开始覆盖的内容除外：

- 账号/会话；
- 项目归属；
- landing / login / settings / billing / admin 最小入口；
- entitlement/usage skeleton；
- provider-neutral payment order 与最小 XPay webhook fulfillment。
