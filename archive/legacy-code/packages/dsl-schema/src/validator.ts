import type {
  DesignDSL,
  DSLAsset,
  DSLElement,
  DSLElementType,
  DSLValidationError,
  DSLValidationResult
} from "./types.js";

const VALID_ELEMENT_TYPES = new Set<DSLElementType>([
  "frame",
  "group",
  "text",
  "shape",
  "image",
  "icon",
  "line"
]);

export function validateDSL(input: unknown): DSLValidationResult {
  const errors: DSLValidationError[] = [];

  if (!isRecord(input)) {
    return {
      valid: false,
      errors: [
        {
          code: "DSL_NOT_OBJECT",
          message: "DSL must be an object.",
          path: "$"
        }
      ],
      warnings: []
    };
  }

  const dsl = input as Partial<DesignDSL>;
  if (dsl.version !== "0.1") {
    errors.push({
      code: "UNSUPPORTED_DSL_VERSION",
      message: 'DSL version must be "0.1".',
      path: "$.version"
    });
  }

  if (!isNonEmptyString(dsl.taskId)) {
    errors.push({
      code: "TASK_ID_REQUIRED",
      message: "taskId is required.",
      path: "$.taskId"
    });
  }

  if (!isRecord(dsl.page)) {
    errors.push({
      code: "PAGE_REQUIRED",
      message: "page is required.",
      path: "$.page"
    });
  } else {
    if (!isPositiveNumber(dsl.page.width)) {
      errors.push({
        code: "PAGE_WIDTH_INVALID",
        message: "page.width must be greater than 0.",
        path: "$.page.width"
      });
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
    errors.push({
      code: "ASSETS_INVALID",
      message: "assets must be an array.",
      path: "$.assets"
    });
  }

  if (!isRecord(dsl.root)) {
    errors.push({
      code: "ROOT_REQUIRED",
      message: "root is required.",
      path: "$.root"
    });
  } else if (dsl.root.type !== "frame") {
    pushError(errors, {
      code: "ROOT_TYPE_INVALID",
      message: "root.type must be frame.",
      path: "$.root.type",
      elementId: typeof dsl.root.id === "string" ? dsl.root.id : undefined
    });
  }

  if (isRecord(dsl.root)) {
    const assetIds = collectAssetIds(Array.isArray(dsl.assets) ? dsl.assets : []);
    const ids = new Set<string>();
    validateElement(dsl.root as Partial<DSLElement>, "$.root", assetIds, ids, errors);
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings: []
  };
}

function validateElement(
  element: Partial<DSLElement>,
  path: string,
  assetIds: Set<string>,
  ids: Set<string>,
  errors: DSLValidationError[]
): void {
  const elementId = typeof element.id === "string" ? element.id : undefined;

  if (!isNonEmptyString(element.id)) {
    errors.push({
      code: "ELEMENT_ID_REQUIRED",
      message: "element.id is required.",
      path: `${path}.id`
    });
  } else if (ids.has(element.id)) {
    errors.push({
      code: "ELEMENT_ID_DUPLICATE",
      message: `Duplicate element id: ${element.id}.`,
      path: `${path}.id`,
      elementId: element.id
    });
  } else {
    ids.add(element.id);
  }

  if (!isValidElementType(element.type)) {
    pushError(errors, {
      code: "ELEMENT_TYPE_INVALID",
      message: `Invalid element type: ${String(element.type)}.`,
      path: `${path}.type`,
      elementId
    });
  }

  if (!isRecord(element.layout)) {
    pushError(errors, {
      code: "LAYOUT_REQUIRED",
      message: "element.layout is required.",
      path: `${path}.layout`,
      elementId
    });
  } else {
    if (!isFiniteNumber(element.layout.x)) {
      pushError(errors, { code: "LAYOUT_X_INVALID", message: "layout.x must be a number.", path: `${path}.layout.x`, elementId });
    }
    if (!isFiniteNumber(element.layout.y)) {
      pushError(errors, { code: "LAYOUT_Y_INVALID", message: "layout.y must be a number.", path: `${path}.layout.y`, elementId });
    }
    if (!isPositiveNumber(element.layout.width)) {
      pushError(errors, { code: "LAYOUT_WIDTH_INVALID", message: "layout.width must be greater than 0.", path: `${path}.layout.width`, elementId });
    }
    if (!isPositiveNumber(element.layout.height)) {
      pushError(errors, { code: "LAYOUT_HEIGHT_INVALID", message: "layout.height must be greater than 0.", path: `${path}.layout.height`, elementId });
    }
  }

  if (element.type === "text" && !isNonEmptyString(element.content?.text)) {
    pushError(errors, {
      code: "TEXT_CONTENT_REQUIRED",
      message: "text element requires content.text.",
      path: `${path}.content.text`,
      elementId
    });
  }

  if (element.type === "image") {
    if (!isRecord(element.source) || (!("assetId" in element.source) && !("url" in element.source))) {
      pushError(errors, {
        code: "IMAGE_SOURCE_REQUIRED",
        message: "image element requires source.assetId or source.url.",
        path: `${path}.source`,
        elementId
      });
    } else if ("assetId" in element.source && typeof element.source.assetId === "string" && !assetIds.has(element.source.assetId)) {
      pushError(errors, {
        code: "ASSET_NOT_FOUND",
        message: `Image assetId not found: ${element.source.assetId}.`,
        path: `${path}.source.assetId`,
        elementId
      });
    }
  }

  if (element.type === "icon") {
    if (!isBuiltinIconSource(element.source)) {
      pushError(errors, {
        code: "ICON_SOURCE_REQUIRED",
        message: "icon element requires source.kind builtin_svg and source.iconName.",
        path: `${path}.source`,
        elementId
      });
    }
  }

  if (element.children !== undefined && !Array.isArray(element.children)) {
    pushError(errors, {
      code: "CHILDREN_INVALID",
      message: "children must be an array when present.",
      path: `${path}.children`,
      elementId
    });
  }

  if (Array.isArray(element.children)) {
    element.children.forEach((child, index) => {
      validateElement(child, `${path}.children[${index}]`, assetIds, ids, errors);
    });
  }
}

function collectAssetIds(assets: unknown[]): Set<string> {
  const ids = new Set<string>();
  for (const asset of assets) {
    if (isRecord(asset) && typeof asset.assetId === "string") {
      ids.add(asset.assetId);
    }
  }
  return ids;
}

function isValidElementType(value: unknown): value is DSLElementType {
  return typeof value === "string" && VALID_ELEMENT_TYPES.has(value as DSLElementType);
}

function isBuiltinIconSource(value: unknown): value is { kind: "builtin_svg"; iconName: string } {
  return isRecord(value) && value.kind === "builtin_svg" && isNonEmptyString(value.iconName);
}

function pushError(
  errors: DSLValidationError[],
  error: Omit<DSLValidationError, "elementId"> & { elementId?: string | undefined }
): void {
  const next: DSLValidationError = {
    code: error.code,
    message: error.message
  };
  if (error.path !== undefined) {
    next.path = error.path;
  }
  if (error.elementId !== undefined) {
    next.elementId = error.elementId;
  }
  errors.push(next);
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
