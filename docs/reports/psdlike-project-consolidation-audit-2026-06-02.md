# PSD-like Project Consolidation Audit 2026-06-02

## Conclusion

当前仓库里同类路径太多，继续在旧 backend、Go mainline、Go experiment 和 clean Python service 之间来回补丁，会制造不可控分叉。本阶段不删除代码，只给后续收敛定边界。

建议的事实分层：

```text
active keep:
  services/psdlike-python

active/experimental keep:
  services/psdlike-go

reference only:
  services/backend-python

legacy/archive candidate:
  backend

current mainline conflict to resolve later:
  services/backend-go
```

## Path Assessment

`services/psdlike-python` 是当前可用产品路径。它已经拥有 PSD-like layer decomposition、Draft Runtime DSL、preview artifacts、model semantic evidence metadata 和 106.5 的真实 OCR 入口。下一阶段插件接入应优先接它，而不是继续扩展旧 Python preview path。

`services/psdlike-go` 保留为后续性能产品化实验。Go 迁移应该等 Python 模块边界稳定后再做，而不是继续逐函数对照迁移。

`services/backend-python` 只保留为行为 oracle 和参考来源。旧 V1 3000 行实验脚本可以继续用于回归对照，但不再作为产品 runtime 扩展点。

`backend` 是历史 FastAPI preview/reference path。除非有单独计划迁移用户仍需要的能力，否则后续可以归档。

`services/backend-go` 与当前 AGENTS.md 主线存在冲突：仓库文档仍称 Go backend 是主线，但当前实际推进的 PSD-like 产品化路径已经转到 `services/psdlike-python`。这不应在 106.5 阶段硬改，需要 107 插件接入或后续架构文档阶段统一。

## Non-Actions In This Stage

本阶段没有做：

```text
delete old backend
move old backend
change plugin route
change services/backend-go
change old V1 oracle
run model local re-search
```

## Recommended Next Stages

107 应该做插件接入和产品可用路径验证：

```text
Figma plugin
-> services/psdlike-python POST /api/draft-preview
-> Draft Runtime DSL
-> renderer/import into Figma
```

后续 cleanup/archive 应单独做，至少需要：

```text
1. 确认插件已不依赖旧 backend / services/backend-go 的冲突路径。
2. 确认 docs/index.md、AGENTS.md、architecture/runtime.md 已同步新的实际主线。
3. 确认旧路径没有未迁移的 OCR/API/storage 能力。
4. 再决定 archive 或删除。
```

## Risk

最大风险不是代码删除，而是主线叙事不一致：文档仍说 Go backend 是当前主线，用户当前要拿去用的是 PSD-like Python。这个风险应该在插件接入前后解决，否则后续代理会继续把新功能写回错误路径。
