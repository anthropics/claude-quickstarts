import { NextRequest, NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";

export async function POST(request: NextRequest) {
  const user = getCurrentUser();
  if (!isHr(user)) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  let body: { employee_id?: number; template_id?: number };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const { employee_id, template_id } = body;
  if (!employee_id || !template_id) {
    return NextResponse.json({ error: "employee_id and template_id are required." }, { status: 400 });
  }

  const db = getDb();

  const employee = db
    .prepare("SELECT id, start_date, manager_id FROM employees WHERE id = ? AND status = 'active'")
    .get(employee_id) as { id: number; start_date: string; manager_id: number | null } | undefined;
  if (!employee) {
    return NextResponse.json({ error: "Employee not found." }, { status: 404 });
  }

  const template = db
    .prepare("SELECT id FROM onboarding_templates WHERE id = ?")
    .get(template_id) as { id: number } | undefined;
  if (!template) {
    return NextResponse.json({ error: "Template not found." }, { status: 404 });
  }

  // Check for existing instance
  const existing = db
    .prepare("SELECT id FROM onboarding_instances WHERE employee_id = ? AND template_id = ?")
    .get(employee_id, template_id) as { id: number } | undefined;
  if (existing) {
    return NextResponse.json({ error: "An onboarding instance already exists for this employee and template." }, { status: 400 });
  }

  const templateTasks = db
    .prepare("SELECT * FROM onboarding_template_tasks WHERE template_id = ? ORDER BY order_index")
    .all(template_id) as {
    id: number;
    title: string;
    description: string | null;
    assignee_type: string;
    due_offset_days: number;
    order_index: number;
  }[];

  // Find IT assignee (Dan, DevOps)
  const itEmployee = db
    .prepare(
      "SELECT id FROM employees WHERE status = 'active' AND (job_title LIKE '%DevOps%' OR job_title LIKE '%IT%' OR job_title LIKE '%System%') LIMIT 1"
    )
    .get() as { id: number } | undefined;

  // Find HR assignee (Lerato)
  const hrEmployee = db
    .prepare("SELECT id FROM employees WHERE status = 'active' AND role = 'hr' LIMIT 1")
    .get() as { id: number } | undefined;

  const result = db
    .prepare("INSERT INTO onboarding_instances (employee_id, template_id) VALUES (?, ?)")
    .run(employee_id, template_id);

  const instanceId = Number(result.lastInsertRowid);

  const insertTask = db.prepare(`
    INSERT INTO onboarding_tasks
      (instance_id, template_task_id, title, description, assignee_type, assigned_to_id, due_date, status, order_index)
    VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
  `);

  for (const t of templateTasks) {
    const d = new Date(employee.start_date);
    d.setDate(d.getDate() + t.due_offset_days);
    const dueDate = d.toISOString().slice(0, 10);

    let assignedToId: number | null = null;
    if (t.assignee_type === "hr") {
      assignedToId = hrEmployee?.id ?? null;
    } else if (t.assignee_type === "it") {
      assignedToId = itEmployee?.id ?? null;
    } else if (t.assignee_type === "manager") {
      assignedToId = employee.manager_id;
    }
    // new_hire → null (identified by instance)

    insertTask.run(
      instanceId,
      t.id,
      t.title,
      t.description,
      t.assignee_type,
      assignedToId,
      dueDate,
      t.order_index
    );
  }

  logAudit(user.id, "create", "onboarding_instance", instanceId, `employee_id=${employee_id} template_id=${template_id}`);

  return NextResponse.json({ id: instanceId }, { status: 201 });
}
