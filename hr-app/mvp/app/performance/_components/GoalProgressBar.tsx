import { goalProgressLabel, goalProgressPct } from "../_lib/perf";

interface Props {
  metricType: "percentage" | "number" | "boolean";
  currentValue: number;
  targetValue: number;
}

/** Server-renderable progress display for a goal (bar for % / number, badge for boolean). */
export default function GoalProgressBar({ metricType, currentValue, targetValue }: Props) {
  const goal = { metric_type: metricType, current_value: currentValue, target_value: targetValue };
  if (metricType === "boolean") {
    return currentValue >= targetValue ? (
      <span className="badge-green">Done</span>
    ) : (
      <span className="badge-gray">Not done</span>
    );
  }
  const pct = goalProgressPct(goal);
  return (
    <div className="flex min-w-[140px] items-center gap-2">
      <div className="h-2 flex-1 rounded-full bg-gray-200">
        <div className="h-2 rounded-full bg-brand-600" style={{ width: `${pct}%` }} />
      </div>
      <span className="whitespace-nowrap text-xs text-gray-500">{goalProgressLabel(goal)}</span>
    </div>
  );
}
