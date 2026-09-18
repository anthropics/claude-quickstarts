// Sends the request that production customers send all day: a cart with no
// coupon. The service answers 500 and the error lands in Sentry.
const base = process.env.DEMO_APP_URL ?? "http://localhost:4000";

const response = await fetch(`${base}/checkout`, {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify({ items: [{ sku: "mug", priceCents: 1200, quantity: 1 }] }),
});
console.log(`POST /checkout -> ${response.status}`);
