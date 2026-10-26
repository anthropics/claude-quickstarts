import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser } from "@/lib/session";
import type { ExpenseCategory } from "@/lib/types";
import { formatRand, isIsoDate } from "@/app/expenses/_lib/format";
import { monthCategoryTotal } from "@/app/expenses/_lib/data";

export async function POST(request: Request) {
  const user = getCurrentUser();
  const db = getDb();

  let body: {
    category_id?: number;
    amount?: number;
    expense_date?: string;
    description?: string;
    receipt_filename?: string;
  };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const category = db
    .prepare("SELECT * FROM expense_categories WHERE id = ?")
    .get(body.category_id) as ExpenseCategory | undefined;
  if (!category) {
    return NextResponse.json({ error: "Unknown expense category." }, { status: 400 });
  }

  const amount = body.amount;
  if (typeof amount !== "number" || !Number.isFinite(amount) || amount <= 0) {
    return NextResponse.json({ error: "Amount must be greater than zero." }, { status: 400 });
  }

  const expenseDate = body.expense_date;
  if (!isIsoDate(expenseDate)) {
    return NextResponse.json({ error: "Expense date is required (YYYY-MM-DD)." }, { status: 400 });
  }
  const today = new Date().toISOString().slice(0, 10);
  if (expenseDate > today) {
    return NextResponse.json({ error: "Expense date cannot be in the future." }, { status: 400 });
  }

  const description = typeof body.description === "string" ? body.description.trim() : "";
  if (!description) {
    return NextResponse.json({ error: "Description is required." }, { status: 400 });
  }

  const receiptFilename =
    typeof body.receipt_filename === "string" && body.receipt_filename.trim()
      ? body.receipt_filename.trim()
      : null;
  if (category.requires_receipt === 1 && !receiptFilename) {
    return NextResponse.json(
      { error: `A receipt is required for ${category.name} claims — please provide the receipt filename.` },
      { status: 400 }
    );
  }

  // Monthly limit check: pending + approved + reimbursed claims in the expense month.
  if (category.monthly_limit !== null) {
    const month = expenseDate.slice(0, 7);
    const spent = monthCategoryTotal(user.id, category.id, month);
    if (spent + amount > category.monthly_limit) {
      const remaining = Math.max(0, category.monthly_limit - spent);
      return NextResponse.json(
        {
          error:
            `This claim exceeds your ${category.name} budget for ${month}: ` +
            `${formatRand(remaining)} remaining of the ${formatRand(category.monthly_limit)} monthly limit ` +
            `(${formatRand(spent)} already claimed).`,
        },
        { status: 400 }
      );
    }
  }

  const result = db
    .prepare(
      `INSERT INTO expense_claims (employee_id, category_id, amount, expense_date, description, receipt_filename, status, approver_id)
       VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)`
    )
    .run(user.id, category.id, amount, expenseDate, description, receiptFilename, user.manager_id);

  const id = Number(result.lastInsertRowid);
  logAudit(user.id, "create", "expense_claim", id, `${category.code} ${expenseDate} ${formatRand(amount)}`);

  return NextResponse.json({ id, status: "pending" }, { status: 201 });
}
