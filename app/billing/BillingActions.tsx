export function BillingActions({ planId }: { planId: string }) {
  return (
    <div className="billingPlaceholder">
      <div className="billingPlaceholderHeader">
        <strong>支付入口暂未开放</strong>
        <span>目标套餐：{planId.toUpperCase()}</span>
      </div>
      <p>
        账单页先保留额度、套餐和订单结构。正式支付暂不接 XPay，后续会改成链动小铺或新的支付 provider，再把购买链路重新挂上来。
      </p>
    </div>
  );
}
