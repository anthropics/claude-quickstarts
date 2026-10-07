import assert from "node:assert/strict";
import { test } from "node:test";
import { orderTotal } from "../src/checkout.js";

const items = [
  { sku: "mug", priceCents: 1200, quantity: 2 },
  { sku: "sticker", priceCents: 300, quantity: 1 },
];

test("applies a percent-off coupon to the subtotal", () => {
  assert.deepEqual(orderTotal({ items, couponCode: "WELCOME10" }), {
    subtotal: 2700,
    discount: 270,
    total: 2430,
  });
});
