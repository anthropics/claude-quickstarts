// In-process fan-out of turn activity (tool calls, model requests, thinking)
// to whoever is watching a thread right now -- the page's `/api/activity`
// tail. Nothing is stored and nothing is replayed: the chat transcript is the
// record, this is only the progress lane, so a subscriber that attaches
// mid-turn simply sees the rest of the turn.

import type { ActivityItem } from "./managed-agents";

type Subscriber = (item: ActivityItem) => void;

const subscribers = new Map<string, Set<Subscriber>>();

export function publishActivity(threadId: string, item: ActivityItem): void {
  for (const notify of subscribers.get(threadId) ?? []) {
    try {
      notify(item);
    } catch {
      // A broken subscriber (a response torn down between writes) must never
      // take down the agent turn that is publishing.
    }
  }
}

export function subscribeActivity(threadId: string, notify: Subscriber): () => void {
  let set = subscribers.get(threadId);
  if (!set) {
    set = new Set();
    subscribers.set(threadId, set);
  }
  set.add(notify);
  const subscribed = set;
  return () => {
    subscribed.delete(notify);
    // Only remove the map entry if it is still ours: a late second call (the
    // stream's cancel after an enqueue already failed) must not evict a set
    // that a newer subscriber re-created under the same thread ID.
    if (subscribed.size === 0 && subscribers.get(threadId) === subscribed) {
      subscribers.delete(threadId);
    }
  };
}
