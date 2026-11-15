import type { BenefitPlan } from "@/lib/types";

export type BenefitCategory = BenefitPlan["category"];

export const BENEFIT_CATEGORIES: readonly BenefitCategory[] = [
  "medical",
  "retirement",
  "life",
  "disability",
  "wellness",
];

export function isBenefitCategory(value: unknown): value is BenefitCategory {
  return typeof value === "string" && (BENEFIT_CATEGORIES as readonly string[]).includes(value);
}

/** Category badge colours: medical=blue, retirement=green, life=yellow, disability=gray, wellness=green. */
export function categoryBadgeClass(category: string): string {
  switch (category) {
    case "medical":
      return "badge-blue";
    case "retirement":
      return "badge-green";
    case "life":
      return "badge-yellow";
    case "disability":
      return "badge-gray";
    case "wellness":
      return "badge-green";
    default:
      return "badge-gray";
  }
}

export function categoryLabel(category: string): string {
  return category.charAt(0).toUpperCase() + category.slice(1);
}

export function fmtRand(n: number): string {
  return new Intl.NumberFormat("en-ZA", { style: "currency", currency: "ZAR", maximumFractionDigits: 0 }).format(n);
}
