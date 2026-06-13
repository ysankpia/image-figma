import { describe, expect, it } from "vitest";
import { fetchTextStyleBatch } from "../server/psdlike-text-style";

describe("psdlike text style client", () => {
  it("parses successful batch measurements", async () => {
    const calls: string[] = [];
    const fetchImpl = (async (input: string | URL | Request) => {
      calls.push(String(input));
      return new Response(JSON.stringify({
        results: [{
          text: "搜索",
          fontSize: 31,
          fontWeight: 500,
          fontFamily: "PingFang SC",
          color: "#fcfdfc",
          lineHeight: 31,
          textAlign: "center",
          measured: { width: 62, height: 34 },
          source: "psdlike"
        }]
      }), { status: 200, headers: { "content-type": "application/json" } });
    }) as typeof fetch;

    const result = await fetchTextStyleBatch(Buffer.from("png"), [{
      text: "搜索",
      bbox: { x: 770, y: 159, width: 121, height: 62 },
      ownerSurface: {
        bbox: { x: 773, y: 161, width: 116, height: 59 },
        fill: "#0eb12f",
        reason: "filled_control_surface"
      }
    }], {
      provider: "psdlike",
      baseUrl: "http://style.local/",
      timeoutSeconds: 1,
      fetchImpl
    });

    expect(calls).toEqual(["http://style.local/api/text-style-batch"]);
    expect(result).toEqual([{
      fontSize: 31,
      fontWeight: "500",
      fontFamily: "PingFang SC",
      color: "#fcfdfc",
      lineHeight: 31,
      textAlign: "center",
      measured: { width: 62, height: 34 },
      source: "psdlike"
    }]);
  });

  it("fails open when the style service is unavailable", async () => {
    const fetchImpl = (async () => new Response("bad gateway", { status: 502 })) as unknown as typeof fetch;
    const result = await fetchTextStyleBatch(Buffer.from("png"), [{
      text: "搜索",
      bbox: { x: 1, y: 2, width: 30, height: 20 }
    }], {
      provider: "psdlike",
      baseUrl: "http://style.local",
      timeoutSeconds: 1,
      fetchImpl
    });

    expect(result).toBeNull();
  });

  it("returns null immediately for fallback provider", async () => {
    let called = false;
    const fetchImpl = (async () => {
      called = true;
      return new Response("{}");
    }) as unknown as typeof fetch;

    const result = await fetchTextStyleBatch(Buffer.from("png"), [{
      text: "搜索",
      bbox: { x: 1, y: 2, width: 30, height: 20 }
    }], {
      provider: "fallback",
      fetchImpl
    });

    expect(result).toBeNull();
    expect(called).toBe(false);
  });
});
