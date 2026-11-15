"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Icon } from "./icons";

interface Notification {
  id: number;
  title: string;
  body: string | null;
  link: string | null;
  read_at: string | null;
  created_at: string;
}

export default function NotificationBell({ initialUnread }: { initialUnread: number }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(initialUnread);
  const [items, setItems] = useState<Notification[]>([]);

  useEffect(() => {
    setUnread(initialUnread);
  }, [initialUnread]);

  async function toggle() {
    if (!open) {
      const res = await fetch("/api/notifications");
      if (res.ok) {
        const j = await res.json();
        setItems(j.notifications);
      }
    }
    setOpen(!open);
  }

  async function markAllRead() {
    await fetch("/api/notifications", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: "{}" });
    setUnread(0);
    setItems(items.map((i) => ({ ...i, read_at: i.read_at ?? "now" })));
    router.refresh();
  }

  function openItem(n: Notification) {
    fetch("/api/notifications", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: n.id }),
    });
    setOpen(false);
    if (n.link) router.push(n.link);
    router.refresh();
  }

  return (
    <div className="relative">
      <button onClick={toggle} className="relative rounded-lg p-2 hover:bg-gray-100" aria-label="Notifications">
        <Icon name="notifications" size={20} className="text-gray-600" />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-bold text-white">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 z-20 mt-1 max-h-96 w-80 overflow-y-auto rounded-xl border border-gray-200 bg-white shadow-lg">
            <div className="flex items-center justify-between border-b border-gray-100 px-3 py-2">
              <span className="text-sm font-semibold">Notifications</span>
              {unread > 0 && (
                <button onClick={markAllRead} className="text-xs text-brand-600 hover:underline">Mark all read</button>
              )}
            </div>
            {items.length === 0 && <p className="px-3 py-6 text-center text-sm text-gray-400">Nothing yet.</p>}
            {items.map((n) => (
              <button
                key={n.id}
                onClick={() => openItem(n)}
                className={`block w-full border-b border-gray-50 px-3 py-2.5 text-left text-sm hover:bg-gray-50 ${n.read_at ? "opacity-60" : ""}`}
              >
                <span className="block font-medium">{n.title}</span>
                {n.body && <span className="mt-0.5 block text-xs text-gray-500 line-clamp-2">{n.body}</span>}
                <span className="mt-0.5 block text-[10px] text-gray-400">{n.created_at.slice(0, 16)}</span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
