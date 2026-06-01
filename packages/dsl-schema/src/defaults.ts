import type { DSLStyle } from "./types.js";

export const DSL_DEFAULTS = {
  role: "unknown",
  style: {} satisfies DSLStyle,
  children: [],
  meta: {},
  opacity: 1,
  visible: true,
  clipContent: false,
  fontFamily: "PingFang SC",
  fontSize: 14,
  fontWeight: 400,
  color: "#000000",
  textAlign: "left",
  imageFillMode: "fill"
} as const;
