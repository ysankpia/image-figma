import type { DSLAsset, DSLElement } from "@image-figma/dsl-schema";
import type { ResolvedImageSource } from "./types";

export function buildAssetMap(assets: DSLAsset[]): Map<string, DSLAsset> {
  return new Map(assets.map((asset) => [asset.assetId, asset]));
}

export function resolveImageSource(
  element: DSLElement,
  assetMap: Map<string, DSLAsset>,
  assetBaseUrl?: string
): ResolvedImageSource | undefined {
  const source = element.source;
  if (!source || "kind" in source) {
    return undefined;
  }

  if (source.assetId) {
    const asset = assetMap.get(source.assetId);
    if (!asset) {
      return undefined;
    }
    return {
      assetId: asset.assetId,
      url: resolveUrl(source.url ?? asset.url, assetBaseUrl)
    };
  }

  if (source.url) {
    return {
      url: resolveUrl(source.url, assetBaseUrl)
    };
  }

  return undefined;
}

function resolveUrl(url: string, assetBaseUrl?: string): string {
  if (!assetBaseUrl || /^https?:\/\//.test(url)) {
    return url;
  }
  return `${assetBaseUrl.replace(/\/$/, "")}/${url.replace(/^\//, "")}`;
}
