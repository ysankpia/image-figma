import type { RenderContext, RenderError, RenderWarning } from "./types";

export function addWarning(context: RenderContext, warning: RenderWarning): void {
  context.warnings.push(cleanMessage(warning));
}

export function addError(context: RenderContext, error: RenderError): void {
  context.errors.push(cleanMessage(error));
}

function cleanMessage<T extends RenderWarning | RenderError>(message: T): T {
  const next = { code: message.code, message: message.message } as T;
  if (message.elementId !== undefined) {
    next.elementId = message.elementId;
  }
  if (message.path !== undefined) {
    next.path = message.path;
  }
  return next;
}
