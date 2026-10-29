const COUPONS = {
  WELCOME10: { percentOff: 10 },
  LAUNCH25: { percentOff: 25 },
};

// Totals are integer cents so no float rounding reaches a customer's card.
export function orderTotal(order) {
  const subtotal = order.items.reduce((sum, item) => sum + item.priceCents * item.quantity, 0);
  const coupon = COUPONS[order.couponCode];
  const discount = Math.round((subtotal * coupon.percentOff) / 100);
  return { subtotal, discount, total: subtotal - discount };
}
