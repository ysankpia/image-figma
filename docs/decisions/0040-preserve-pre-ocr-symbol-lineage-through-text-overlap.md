# ADR 0040: Preserve Pre-OCR Symbol Lineage Through Text Overlap

## Status

Accepted.

## Context

M29.0.7 correctly blocks plain `text_noise` from object-forming visual side. That exposed a different failure mode: some true small visual candidates already had pre-OCR symbol lineage in M29/M29.1, but M29.0.3 treated high OCR/text overlap as a final `text_noise` demotion. Once that happens, M29.0.7 can only route it as text-owned or audit-only.

The root problem is not a missing page-specific rule. The root problem is that M29.0.3 did not distinguish plain text noise from a lineage-backed symbol/text ownership conflict.

## Decision

Add M29.1.1 as a read-only Pre-OCR Symbol Lineage Audit. It traces M29 node/blocked evidence and M29.1 candidate/group lineage through M29.0.2, M29.0.3, and M29.0.7 to explain where lineage is lost.

Extend M29.1 output with `sourceLineage` for accepted groups, uncertain groups, and eligible blocked candidates. Rejected text-like or image-like merged results do not get surviving visual lineage; they can only record `rejectedLineageReason`.

Allow M29.0.3 to consume M29.1 lineage via optional `--m291-lineage-json`. With no lineage input, M29.0.3 baseline remains unchanged. With lineage input:

```text
high text overlap + no surviving lineage -> text_noise
high text overlap + surviving pre-OCR lineage -> mixed_symbol_text_candidate
high text overlap + rejected text-like lineage -> text_noise
```

M29.0.7 routes `mixed_symbol_text_candidate` as `mixed_or_uncertain` audit-only. It is not text-owned accepted, not visual-owned accepted, and not allowed for object-forming visual side.

## Consequences

- True small visual candidates with pre-OCR lineage remain traceable through OCR conflict.
- OCR/text ownership still owns plain text noise.
- Uncertain lineage does not become a formal visual asset.
- Text-like glyph sequences do not sneak back into visual assets.
- M29.0.3 baseline is preserved when no lineage JSON is supplied.
- M29.0.4 and later stages can keep mixed conflict as audit evidence without reintroducing weak text noise into object-forming visual side.
