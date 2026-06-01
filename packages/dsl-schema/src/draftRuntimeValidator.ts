import type {
  DraftRuntimeAsset,
  DraftRuntimeDSL,
  DraftRuntimeNode,
  DraftRuntimeNodeType,
  DraftRuntimeValidationResult
} from "./draftRuntimeTypes.js";
import type { DSLValidationError, DSLValidationWarning } from "./types.js";

const VALID_NODE_TYPES = new Set<DraftRuntimeNodeType>(["frame", "group", "text", "shape", "image"]);

export function validateDraftRuntimeDSL(input: unknown): DraftRuntimeValidationResult {
  const errors: DSLValidationError[] = [];
  const warnings: DSLValidationWarning[] = [];

  if (!isRecord(input)) {
    return {
      valid: false,
      errors: [{ code: "DRAFT_RUNTIME_DSL_NOT_OBJECT", message: "Draft Runtime DSL must be an object.", path: "$" }],
      warnings: []
    };
  }

  const dsl = input as Partial<DraftRuntimeDSL>;
  if (dsl.version !== "1.0") {
    errors.push({
      code: "UNSUPPORTED_DRAFT_RUNTIME_DSL_VERSION",
      message: 'Draft Runtime DSL version must be "1.0".',
      path: "$.version"
    });
  }
  if (dsl.kind !== "draft_runtime") {
    errors.push({
      code: "DRAFT_RUNTIME_KIND_INVALID",
      message: 'Draft Runtime DSL kind must be "draft_runtime".',
      path: "$.kind"
    });
  }
  if (!isNonEmptyString(dsl.taskId)) {
    errors.push({ code: "TASK_ID_REQUIRED", message: "taskId is required.", path: "$.taskId" });
  }

  if (!isRecord(dsl.page)) {
    errors.push({ code: "PAGE_REQUIRED", message: "page is required.", path: "$.page" });
  } else {
    if (!isPositiveNumber(dsl.page.width)) {
      errors.push({ code: "PAGE_WIDTH_INVALID", message: "page.width must be greater than 0.", path: "$.page.width" });
    }
    if (!isPositiveNumber(dsl.page.height)) {
      errors.push({
        code: "PAGE_HEIGHT_INVALID",
        message: "page.height must be greater than 0.",
        path: "$.page.height"
      });
    }
  }

  if (!Array.isArray(dsl.assets)) {
    errors.push({ code: "ASSETS_INVALID", message: "assets must be an array.", path: "$.assets" });
  }

  if (!isRecord(dsl.root)) {
    errors.push({ code: "ROOT_REQUIRED", message: "root is required.", path: "$.root" });
  } else if (dsl.root.type !== "frame" && dsl.root.type !== "group") {
    pushError(errors, {
      code: "ROOT_TYPE_INVALID",
      message: "root.type must be frame or group.",
      path: "$.root.type",
      elementId: typeof dsl.root.id === "string" ? dsl.root.id : undefined
    });
  }

  if (isRecord(dsl.root)) {
    const assetIds = collectAssetIds(Array.isArray(dsl.assets) ? dsl.assets : []);
    const ids = new Set<string>();
    validateNode(dsl.root as Partial<DraftRuntimeNode>, "$.root", assetIds, ids, errors, warnings);
  }

  return { valid: errors.length === 0, errors, warnings };
}

function validateNode(
  node: Partial<DraftRuntimeNode>,
  path: string,
  assetIds: Set<string>,
  ids: Set<string>,
  errors: DSLValidationError[],
  warnings: DSLValidationWarning[]
): void {
  const elementId = typeof node.id === "string" ? node.id : undefined;

  if (!isNonEmptyString(node.id)) {
    errors.push({ code: "ELEMENT_ID_REQUIRED", message: "node.id is required.", path: `${path}.id` });
  } else if (ids.has(node.id)) {
    pushError(errors, {
      code: "ELEMENT_ID_DUPLICATE",
      message: `Duplicate node id: ${node.id}.`,
      path: `${path}.id`,
      elementId: node.id
    });
  } else {
    ids.add(node.id);
  }

  if (!isValidNodeType(node.type)) {
    pushError(errors, {
      code: "ELEMENT_TYPE_INVALID",
      message: `Invalid Draft Runtime node type: ${String(node.type)}.`,
      path: `${path}.type`,
      elementId
    });
  }

  if (!isRecord(node.bbox)) {
    pushError(errors, { code: "BBOX_REQUIRED", message: "node.bbox is required.", path: `${path}.bbox`, elementId });
  } else {
    if (!isFiniteNumber(node.bbox.x)) {
      pushError(errors, { code: "BBOX_X_INVALID", message: "bbox.x must be a number.", path: `${path}.bbox.x`, elementId });
    }
    if (!isFiniteNumber(node.bbox.y)) {
      pushError(errors, { code: "BBOX_Y_INVALID", message: "bbox.y must be a number.", path: `${path}.bbox.y`, elementId });
    }
    if (!isPositiveNumber(node.bbox.width)) {
      pushError(errors, {
        code: "BBOX_WIDTH_INVALID",
        message: "bbox.width must be greater than 0.",
        path: `${path}.bbox.width`,
        elementId
      });
    }
    if (!isPositiveNumber(node.bbox.height)) {
      pushError(errors, {
        code: "BBOX_HEIGHT_INVALID",
        message: "bbox.height must be greater than 0.",
        path: `${path}.bbox.height`,
        elementId
      });
    }
  }

  if (node.type === "text" && !isNonEmptyString(node.text?.characters)) {
    pushError(errors, {
      code: "TEXT_CONTENT_REQUIRED",
      message: "text node requires text.characters.",
      path: `${path}.text.characters`,
      elementId
    });
  }

  if (node.type === "image") {
    const image = node.image;
    if (!isRecord(image) || (!isNonEmptyString(image.assetId) && !isNonEmptyString(image.url))) {
      pushWarning(warnings, {
        code: "IMAGE_SOURCE_MISSING",
        message: "image node has no assetId or url and will render as a placeholder.",
        path: `${path}.image`,
        elementId
      });
    } else if (isNonEmptyString(image.assetId) && !assetIds.has(image.assetId)) {
      pushError(errors, {
        code: "ASSET_NOT_FOUND",
        message: `Image assetId not found: ${image.assetId}.`,
        path: `${path}.image.assetId`,
        elementId
      });
    }
  }

  if (node.children !== undefined && !Array.isArray(node.children)) {
    pushError(errors, {
      code: "CHILDREN_INVALID",
      message: "children must be an array when present.",
      path: `${path}.children`,
      elementId
    });
  }
  if (Array.isArray(node.children)) {
    node.children.forEach((child, index) => {
      validateNode(child, `${path}.children[${index}]`, assetIds, ids, errors, warnings);
    });
  }
}

function collectAssetIds(assets: unknown[]): Set<string> {
  const ids = new Set<string>();
  for (const asset of assets) {
    if (isRecord(asset) && typeof (asset as Partial<DraftRuntimeAsset>).assetId === "string") {
      ids.add((asset as Partial<DraftRuntimeAsset>).assetId as string);
    }
  }
  return ids;
}

function isValidNodeType(value: unknown): value is DraftRuntimeNodeType {
  return typeof value === "string" && VALID_NODE_TYPES.has(value as DraftRuntimeNodeType);
}

function pushError(
  errors: DSLValidationError[],
  error: Omit<DSLValidationError, "elementId"> & { elementId?: string | undefined }
): void {
  const next: DSLValidationError = { code: error.code, message: error.message };
  if (error.path !== undefined) {
    next.path = error.path;
  }
  if (error.elementId !== undefined) {
    next.elementId = error.elementId;
  }
  errors.push(next);
}

function pushWarning(
  warnings: DSLValidationWarning[],
  warning: Omit<DSLValidationWarning, "elementId"> & { elementId?: string | undefined }
): void {
  const next: DSLValidationWarning = { code: warning.code, message: warning.message };
  if (warning.path !== undefined) {
    next.path = warning.path;
  }
  if (warning.elementId !== undefined) {
    next.elementId = warning.elementId;
  }
  warnings.push(next);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isPositiveNumber(value: unknown): value is number {
  return isFiniteNumber(value) && value > 0;
}
