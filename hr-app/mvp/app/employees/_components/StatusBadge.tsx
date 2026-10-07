import { labelFor, STATUSES } from "./labels";

const CLASSES: Record<string, string> = {
  active: "badge-green",
  on_leave: "badge-yellow",
  terminated: "badge-red",
};

export default function StatusBadge({ status }: { status: string }) {
  return <span className={CLASSES[status] ?? "badge-gray"}>{labelFor(STATUSES, status)}</span>;
}
