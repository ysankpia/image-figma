# Figma MCP Uploaded Page Prototype

- 日期：2026-05-22
- 状态：test artifact

## Purpose

This prototype records a Figma MCP design-to-code experiment for node `1442:1706` in file `NQoqMWv8BUbqtNq2xvlrJH`.

It is intentionally kept as a local documentation/test artifact. It verifies that an already-structured Figma layer tree can be translated into a static HTML/CSS page with downloaded image assets.

## Boundary

This prototype does not replace the main PNG-to-Figma pipeline.

It proves:

```text
existing Figma layer tree -> HTML/CSS replay is feasible
```

It does not prove:

```text
raw PNG -> editable Figma structure can skip M29/M30/M37/M38/M39
```

## Files

- `index.html`: static absolute-position replay.
- `assets/figma-reference.png`: Figma MCP screenshot reference.
- `assets/*.png`: image assets downloaded from the Figma MCP asset endpoint.

## Notes

The asset URLs from Figma MCP are short-lived. The PNG files are committed here so this prototype remains inspectable after those URLs expire.
