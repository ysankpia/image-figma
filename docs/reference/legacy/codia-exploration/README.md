# Codia Exploration Legacy Documents

本目录保存 Codia 逆向探索阶段的旧文档。它们是历史背景，不是当前实现合同。

当前 source truth：

```text
docs/product/codia_compiler_buildability_audit_zh.md
docs/plans/archive/deferred/089-go-codia-like-compiler-rebuild.md
docs/bugs/open/017-codia-like-beta-ui-role-detector-gap.md
docs/reference/codia-samples/*.canvas.json
docs/reference/codia-samples/images/*.png
```

归档文件：

| 文件 | 原位置 | 说明 |
| --- | --- | --- |
| [codia-compiler-reverse-spec-v0.1.md](codia-compiler-reverse-spec-v0.1.md) | `docs/reference/codia-compiler-reverse-spec-v0.1.md` | raw Codia canvas reverse spec 草案，已被产品审计和 089 主线吸收。 |
| [codia-compiler-reverse-spec.md](codia-compiler-reverse-spec.md) | `docs/reference/codia-compiler-reverse-spec.md` | 早期中文 Codia compiler 逆向草案。 |
| [codia-fig-reverse-engineering.md](codia-fig-reverse-engineering.md) | `docs/reference/codia-fig-reverse-engineering.md` | 早期 `.fig` / canvas 解析笔记，包含后续被证伪或降级的纯几何判断。 |
| [codia-visual-element-schema.md](codia-visual-element-schema.md) | `docs/reference/codia-visual-element-schema.md` | Codia VisualElement / API schema 逆向参考，不是当前 Go compiler runtime 合同。 |
| [full.md](full.md) | `docs/reference/full.md` | Codia API 文档快照，保留用于历史 API 追溯。 |

不要从本目录恢复 active implementation rules。需要实现或修复 Go Codia-like compiler 时，先读当前主线文档和 raw `.canvas.json` samples。
