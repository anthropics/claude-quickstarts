"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "./icons";

export default function NavLink({ href, label, icon }: { href: string; label: string; icon: string }) {
  const pathname = usePathname();
  const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
  return (
    <Link
      href={href}
      className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium ${
        active ? "bg-brand-600 text-white" : "text-gray-600 hover:bg-gray-100"
      }`}
    >
      <Icon name={icon} size={18} className={active ? "text-white" : "text-gray-400"} />
      {label}
    </Link>
  );
}
