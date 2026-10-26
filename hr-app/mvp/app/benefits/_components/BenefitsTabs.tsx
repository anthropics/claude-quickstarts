import Link from "next/link";

interface Props {
  active: "my" | "plans" | "enrolments" | "costs";
  showAdmin: boolean;
}

export default function BenefitsTabs({ active, showAdmin }: Props) {
  const tabs: { key: Props["active"]; href: string; label: string; show: boolean }[] = [
    { key: "my", href: "/benefits", label: "My Benefits", show: true },
    { key: "plans", href: "/benefits/admin", label: "Plans", show: showAdmin },
    { key: "enrolments", href: "/benefits/admin/enrolments", label: "Enrolments", show: showAdmin },
    { key: "costs", href: "/benefits/admin/costs", label: "Cost Report", show: showAdmin },
  ];
  return (
    <div className="flex gap-1 border-b border-gray-200">
      {tabs
        .filter((t) => t.show)
        .map((t) => (
          <Link
            key={t.key}
            href={t.href}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium ${
              active === t.key
                ? "border-brand-600 text-brand-600"
                : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700"
            }`}
          >
            {t.label}
          </Link>
        ))}
    </div>
  );
}
