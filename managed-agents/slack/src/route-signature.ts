import { createHmac, timingSafeEqual } from "crypto";

// Session metadata says where to post the reply, and anyone with credentials
// for this Anthropic workspace can write metadata on a session of their own,
// on this same agent. So the bridge signs the route it stored, with a secret
// that never leaves this process, and the idle webhook only trusts routes that
// carry a valid signature.
//
// The signature covers the session ID. Metadata is readable by the same people
// who can forge it, so a signature over the route alone could be copied onto
// another session. Bound to the ID, it is only good for the session it was
// made for.
//
// The signature also covers an issued-at time, and verifyRoute rejects a route
// older than MAX_AGE_SECONDS. The route is deleted after one delivery, but a
// delivery that keeps failing with retryable errors would otherwise leave it
// live with no end. 24 hours is far past any webhook retry schedule.
//
// The key is derived from SLACK_SIGNING_SECRET, which this bridge already
// holds and Anthropic never sees, so there is nothing new to configure.
function key(): Buffer {
  return createHmac("sha256", process.env.SLACK_SIGNING_SECRET!)
    .update("managed-agents-bridge/route-signature/v1")
    .digest();
}

export const MAX_AGE_SECONDS = 24 * 60 * 60;

export function signRoute(sessionId: string, a: string, b: string, issuedAt: string): string {
  return createHmac("sha256", key()).update(`${sessionId}|${a}|${b}|${issuedAt}`).digest("hex");
}

export function verifyRoute(
  sessionId: string,
  a: string,
  b: string,
  issuedAt: string | undefined,
  signature: string | undefined,
): boolean {
  if (!signature || !issuedAt || !/^\d{1,12}$/.test(issuedAt)) return false;
  const age = Math.floor(Date.now() / 1000) - Number(issuedAt);
  if (age < -60 || age > MAX_AGE_SECONDS) return false;
  const expected = Buffer.from(signRoute(sessionId, a, b, issuedAt));
  const given = Buffer.from(signature);
  return expected.length === given.length && timingSafeEqual(expected, given);
}
