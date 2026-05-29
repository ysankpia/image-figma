---
name: codia-text-background-strategy-and-container-ratio-audit
status: active
created: 2026-05-29
scope: services/backend-go VisualTree spatial grouping / container ratio optimization
---

# Codia Text/Button 策略逆向 & Container Ratio 审计结论

## 1. Codia 的 Text/Button 处理策略（从真实 canvas JSON 逆向确认）

Codia **从不**为单个 Text 创建 1:1 的 background wrapper 容器。

### Codia 的 Button 模式

```
FRAME "Button" (175x46)
├── TEXT "uinotes.com" (120x20)
├── ROUNDED_RECTANGLE "Image" (23x22)     ← icon，兄弟
└── ROUNDED_RECTANGLE "Background" (166x41) ← 背景是兄弟，不是包装器
```

关键特征：
- 背景是 ROUNDED_RECTANGLE **兄弟节点**，不是父容器
- Button 容器通常有 3 children（text + background_rect + icon/decoration）
- Button bbox 比 TEXT 大（有 padding）
- 背景矩形是**真实节点**（有圆角、填充色），不是凭空合成的

### Codia 的区域分组模式

多个 TEXT 直接平铺在 FRAME 里，和 ROUNDED_RECTANGLE、其他 FRAME 混合：

```
FRAME "Groups" (610x752)
├── TEXT "会员专区"
├── TEXT "开通礼包"
├── TEXT "价值13元开通即回本"
├── FRAME "Groups" (621x131)
├── FRAME "Button" (563x74)
└── ROUNDED_RECTANGLE "Image" (617x694)  ← 大背景
```

### 我们的 text_background_group 的问题

`pairTextBackedForeground` 是无证据猜测器。它在 `splitBackgroundLeaves` 之后运行——此时有 physical background 的节点已经被正确处理了。剩下的 Text 节点没有任何背景证据，但仍然凭宽高比（2.5≤aspect≤6 且 width<50% parent）创建 synthetic background wrapper。

### 数据来源

- 从 `tencent-comic-018.canvas.json` 和 `tencent-comic-022.canvas.json` 逆向确认
- eval trace 验证：matched text_background_group 全部匹配 Codia 的 "Button" 类型 FRAME
- t018 有 22 个 TEXT+RECT 容器（Button），t022 有 14 个

---

## 2. Container Ratio 审计结论（2026-05-29）

当前状态：`avg_score=0.843, min_score=0.800, avg_container_ratio=1.332`

### 已完成的安全折叠

| 规则 | 效果 | commit |
|---|---|---|
| text_background_group (nearPeer==0 && areaRatio<0.2) | 砍掉部分伪背景 | ee29eb9 |
| spatial_group (projection, no text, shortSide<=20) | 砍掉薄片碎片 | ee29eb9 |
| Layer (no text, shortSide<=8) | 砍掉 render wrapper | e32d689 |

### 四图汇总审计数据（184 selected, 111 matched, 73 extra）

```
spatial_group:           matched=41 extra=38 precision=0.519
Layer:                   matched=14 extra=15 precision=0.483
text_background_group:   matched=9  extra=14 precision=0.391
vertical_pair_group:     matched=34 extra=8  precision=0.810
contained_pair_group:    matched=5  extra=4  precision=0.556
```

### spatial_group 无单一区分信号

spatial_group 的 matched/extra 在每个维度上都是 ~50/50 混合：

```
parentReason:
  xycut_y              matched=23 extra=24 precision=0.489
  xycut_x              matched=11 extra=11 precision=0.500
  neighbor_component   matched=7  extra=3  precision=0.700

containsText:
  true                 matched=39 extra=31 precision=0.557
  false                matched=2  extra=7  precision=0.222

shortSideBin:
  041-080              matched=12 extra=14 precision=0.462
  081+                 matched=22 extra=13 precision=0.629
  021-040              matched=7  extra=11 precision=0.389
```

没有单一几何特征能干净分开 matched 和 extra。继续扩大几何阈值折叠是死路。

### 单图瓶颈

- **t018**（ratio=1.756）：spatial extra=15, text_background extra=6, vertical_pair extra=4
- **t022**（ratio=1.393）：spatial extra=12, text_background extra=5, xycut_x precision=0.333
- **荔枝**（ratio=1.094）：已达标
- **闲鱼**（ratio=1.086）：已达标

### 已确认的死路

- gap 显著性过滤：阶跃函数，1.3-1.8 无效，2.0 崩溃
- spatialDepth >= 1 全跳 xycut：t018 recall 0.829→0.756
- minWrap=3：t018 recall 0.829→0.780
- spatial_group shortSide<=32 四图汇总：precision=0.833 但 matchedLost=1

### 下一步正确方向

1. **短期**：permission gate 加 nearby-image 证据检查——只保留兄弟中有 Image 且 bbox 重叠的 text_background_group
2. **中期**：`pairTextBackedForeground` 从几何猜测改为 evidence-gated——只有 Text 附近有 physical token 时才创建
3. **长期**：text_background_group 概念不应存在；Codia Button 应由 containment 阶段正确处理
