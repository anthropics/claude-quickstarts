import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import type { Employee } from "@/lib/types";

const GOAL_TYPES = ["individual", "team", "company"];
const METRIC_TYPES = ["percentage", "number", "boolean"];

export async function POST(request: Request) {
  const user = getCurrentUser();
  const db = getDb();

  let body: {
    title?: unknown;
    description?: unknown;
    employee_id?: unknown;
    type?: unknown;
    metric_type?: unknown;
    target_value?: unknown;
    due_date?: unknown;
  };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const title = typeof body.title === "string" ? body.title.trim() : "";
  if (!title) {
    return NextResponse.json({ error: "Title is required." }, { status: 400 });
  }
  const description =
    typeof body.description === "string" && body.description.trim() ? body.description.trim() : null;

  const type = typeof body.type === "string" && GOAL_TYPES.includes(body.type) ? body.type : "individual";
  const metricType =
    typeof body.metric_type === "string" && METRIC_TYPES.includes(body.metric_type)
      ? body.metric_type
      : "percentage";

  let targetValue: number;
  if (metricType === "boolean") {
    targetValue = 1;
  } else {
    targetValue = Number(body.target_value);
    if (!Number.isFinite(targetValue) || targetValue <= 0) {
      return NextResponse.json({ error: "Target value must be a positive number." }, { status: 400 });
    }
  }

  const dueDate =
    typeof body.due_date === "string" && /^\d{4}-\d{2}-\d{2}$/.test(body.due_date) ? body.due_date : null;

  const employeeId = body.employee_id != null && body.employee_id !== "" ? Number(body.employee_id) : user.id;
  if (!Number.isInteger(employeeId)) {
    return NextResponse.json({ error: "Invalid employee id." }, { status: 400 });
  }
  if (employeeId !== user.id) {
    const owner = db.prepare("SELECT * FROM employees WHERE id = ?").get(employeeId) as Employee | undefined;
    if (!owner) {
      return NextResponse.json({ error: "Employee not found." }, { status: 404 });
    }
    if (!isHr(user) && owner.manager_id !== user.id) {
      return NextResponse.json(
        { error: "You can only create goals for yourself or your direct reports." },
        { status: 403 }
      );
    }
  }

  const result = db
    .prepare(
      `INSERT INTO goals (employee_id, title, description, type, metric_type, target_value, current_value, due_date, status)
       VALUES (?, ?, ?, ?, ?, ?, 0, ?, 'not_started')`
    )
    .run(employeeId, title, description, type, metricType, targetValue, dueDate);

  const id = Number(result.lastInsertRowid);
  logAudit(user.id, "create", "goal", id, title);
  return NextResponse.json({ id }, { status: 201 });
}
