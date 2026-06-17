import crypto from "node:crypto";
import { httpError } from "./errors";
import { xpayBaseUrl, xpayKey, xpayNotifyUrl, xpayPid, xpayReturnUrl } from "./config";

export type XPayOrder = {
  payUrl: string;
  params: Record<string, string>;
};

export type XPayNotify = {
  pid: string;
  trade_no: string;
  out_trade_no: string;
  type: string;
  name: string;
  money: string;
  trade_status: string;
  sign: string;
  sign_type: string;
};

export function createXPayOrder(input: {
  outTradeNo: string;
  name: string;
  money: number;
  type?: string;
}): XPayOrder | null {
  if (!xpayPid || !xpayKey || !xpayBaseUrl || !xpayNotifyUrl || !xpayReturnUrl) return null;
  const params = {
    pid: xpayPid,
    type: input.type || "alipay",
    out_trade_no: input.outTradeNo,
    notify_url: xpayNotifyUrl,
    return_url: xpayReturnUrl,
    name: input.name,
    money: input.money.toFixed(2),
    sign: "",
    sign_type: "MD5"
  };
  const sign = signXPayParams(params);
  const finalParams = { ...params, sign };
  return {
    payUrl: `${xpayBaseUrl}/submit.php`,
    params: finalParams
  };
}

export function verifyXPayNotify(notify: XPayNotify): boolean {
  if (!xpayKey) return false;
  const expected = signXPayParams({
    pid: notify.pid,
    trade_no: notify.trade_no,
    out_trade_no: notify.out_trade_no,
    type: notify.type,
    name: notify.name,
    money: notify.money,
    trade_status: notify.trade_status,
    sign: "",
    sign_type: notify.sign_type
  });
  return expected === notify.sign;
}

export function signXPayForTest(params: Record<string, string>): string {
  if (process.env.NODE_ENV !== "test" && !process.env.VITEST && process.env.SLICE_STUDIO_ALLOW_XPAY_TEST_SIGN !== "true") {
    throw httpError(403, "XPay test signing is disabled");
  }
  return signXPayParams(params);
}

export function isXPaySuccessStatus(status: string): boolean {
  return ["TRADE_SUCCESS", "TRADE_FINISHED", "WAIT_BUYER_PAY"].includes(status);
}

function signXPayParams(params: Record<string, string>): string {
  const parts = Object.entries(params)
    .filter(([key, value]) => key !== "sign" && key !== "sign_type" && value !== "" && value !== undefined && value !== null)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, value]) => `${key}=${value}`);
  const payload = `${parts.join("&")}&key=${xpayKey}`;
  return crypto.createHash("md5").update(payload).digest("hex");
}
