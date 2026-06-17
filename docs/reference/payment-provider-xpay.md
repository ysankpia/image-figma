# XPay / 易支付 provider notes

This document records the current external-payment candidate discussed for Slice Studio production launch. It is not the final product contract. The internal product truth remains the Slice Studio user, project, entitlement, and usage model.

## Candidate

Observed provider documentation:

- [XPay 支付系统 / epay_submit](https://x.yhhrun.cn/doc/epay_submit)

CodeGraph review of the public site indicates it is an XPay / 易支付 / 码支付 style payment system with:

- a public product home;
- a `/doc` documentation route;
- a `/demo` payment test route;
- a `/pay/status` route;
- a `/cashier/:key` cashier route;
- a `/user` merchant-center route;
- order and callback-related API names such as `/order/create-cashier`, `/order/status`, `/order/info`, `/order/callback`, `/order/qrcode`, `/pay/conf`, `/pay/types`, `/pay/create-test-order`, and `/log/notify`.

## Why this is acceptable for the first launch

This provider can be used as a first payment adapter if Slice Studio keeps the real source of truth in its own database and entitlement tables.

That means:

- Slice Studio creates its own payment order first;
- the provider only handles collection and callback;
- Slice Studio verifies the callback on the server;
- Slice Studio writes its own payment event and entitlement records;
- the UI only reflects server-verified order state.

## What must stay in Slice Studio

Do not outsource these to the payment provider:

- user identity;
- project ownership;
- plan/entitlement state;
- usage metering;
- audit log;
- grant/revoke rules;
- order fulfillment idempotency.

## Required internal contract

The internal product contract should stay provider-neutral:

```text
checkout request
-> local payment order
-> provider redirect or cashier url
-> provider callback/webhook
-> signature verification
-> payment event row
-> entitlement update
-> gated product action
```

Required internal states:

```text
free
trial
active
past_due
paused
canceled
expired
refunded
manual_grant
```

## Required server checks

For a payment adapter based on XPay / 易支付, Slice Studio still needs:

- a provider-neutral `payment_orders` table;
- a raw `payment_events` table;
- webhook signature verification;
- amount and order-id validation;
- idempotent fulfillment;
- an entitlement recalculation step;
- a failure log path for webhook and replay problems;
- a manual repair path for admin/operator use.

## Early implementation recommendation

For the first launch, use the provider in the simplest safe mode:

1. user selects a plan or recharge package in Slice Studio;
2. Slice Studio creates a local order;
3. Slice Studio redirects to the provider or returns a cashier URL;
4. provider callback is verified server-side;
5. Slice Studio grants credits or subscription entitlement;
6. user sees the updated status in billing and usage pages.

If the provider later exposes a reliable order query API, add it as a repair/reconciliation tool only. Do not make the product depend on client-side polling.
