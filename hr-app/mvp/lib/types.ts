export type Role = "admin" | "hr" | "manager" | "employee";

export interface Employee {
  id: number;
  employee_number: string;
  first_name: string;
  last_name: string;
  work_email: string;
  personal_email: string | null;
  phone: string | null;
  date_of_birth: string | null;
  gender: string | null;
  nationality: string | null;
  job_title: string;
  department_id: number | null;
  manager_id: number | null;
  employment_type: string;
  start_date: string;
  probation_end_date: string | null;
  status: string;
  role: Role;
  emergency_contact_name: string | null;
  emergency_contact_phone: string | null;
  address: string | null;
  must_change_password?: number;
  last_login_at?: string | null;
  medical_aid_members?: number;
}

export interface Department {
  id: number;
  name: string;
  parent_id: number | null;
  head_employee_id: number | null;
}

export interface LeaveType {
  id: number;
  name: string;
  code: string;
  colour: string;
  annual_entitlement_days: number;
  paid: number;
  probation_restricted: number;
  negative_balance_allowed: number;
}

export interface LeaveRequest {
  id: number;
  employee_id: number;
  leave_type_id: number;
  start_date: string;
  end_date: string;
  days: number;
  notes: string | null;
  status: "pending" | "approved" | "rejected" | "cancelled";
  approver_id: number | null;
  decided_at: string | null;
  decision_note: string | null;
  created_at: string;
}

export interface ClockEvent {
  id: number;
  employee_id: number;
  type: "clock_in" | "clock_out" | "break_start" | "break_end";
  timestamp: string;
  method: string;
}

export interface Timesheet {
  id: number;
  employee_id: number;
  period_start: string;
  period_end: string;
  status: "draft" | "submitted" | "approved" | "rejected";
  total_minutes: number;
  overtime_minutes: number;
  submitted_at: string | null;
  decided_at: string | null;
}

// ── Phase 2: Payroll ─────────────────────────────────────────────────────────

export interface EarningsCode {
  id: number;
  name: string;
  code: string;
  type: "basic" | "allowance" | "bonus";
  taxable: number;
}

export interface DeductionCode {
  id: number;
  name: string;
  code: string;
  calc_type: "percentage" | "fixed";
  rate: number;
  pre_tax: number;
  statutory: number;
}

export interface PayrollRun {
  id: number;
  period_start: string;
  period_end: string;
  payment_date: string;
  status: "draft" | "approved" | "paid" | "cancelled";
  notes: string | null;
  created_by: number | null;
  approved_by: number | null;
  approved_at: string | null;
  created_at: string;
}

export interface PayslipLine {
  label: string;
  amount: number;
  type: "earning" | "deduction";
}

export interface Payslip {
  id: number;
  payroll_run_id: number;
  employee_id: number;
  gross_pay: number;
  income_tax: number;
  uif_employee: number;
  total_deductions: number;
  net_pay: number;
  lines: string; // JSON string of PayslipLine[]
}

// ── Phase 2: ATS ─────────────────────────────────────────────────────────────

export type ApplicationStage =
  | "applied" | "screening" | "phone_screen" | "interview"
  | "assessment" | "offer" | "hired" | "rejected" | "withdrawn";

export interface JobPosting {
  id: number;
  title: string;
  department_id: number | null;
  location: string | null;
  description: string | null;
  requirements: string | null;
  employment_type: string;
  status: "draft" | "open" | "closed" | "on_hold";
  posted_at: string | null;
  closes_at: string | null;
  created_by: number | null;
  created_at: string;
}

export interface Candidate {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  phone: string | null;
  cv_filename: string | null;
  source: string;
  created_at: string;
}

export interface Application {
  id: number;
  job_posting_id: number;
  candidate_id: number;
  stage: ApplicationStage;
  notes: string | null;
  rejection_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface Interview {
  id: number;
  application_id: number;
  scheduled_at: string;
  duration_minutes: number;
  format: "video" | "in_person" | "phone";
  interviewer_ids: string; // JSON number[]
  notes: string | null;
  rating: number | null;
  feedback_submitted_at: string | null;
  created_at: string;
}

export interface Offer {
  id: number;
  application_id: number;
  salary: number;
  start_date: string;
  expiry_date: string;
  status: "draft" | "sent" | "accepted" | "rejected" | "expired";
  notes: string | null;
  created_at: string;
}

// ── Phase 2: Onboarding ───────────────────────────────────────────────────────

export interface OnboardingTemplate {
  id: number;
  name: string;
  description: string | null;
  department_id: number | null;
}

export interface OnboardingTemplateTask {
  id: number;
  template_id: number;
  title: string;
  description: string | null;
  assignee_type: "hr" | "it" | "manager" | "new_hire";
  due_offset_days: number;
  order_index: number;
}

export interface OnboardingInstance {
  id: number;
  employee_id: number;
  template_id: number;
  created_at: string;
  completed_at: string | null;
}

export interface OnboardingTask {
  id: number;
  instance_id: number;
  template_task_id: number | null;
  title: string;
  description: string | null;
  assignee_type: "hr" | "it" | "manager" | "new_hire";
  assigned_to_id: number | null;
  due_date: string | null;
  status: "pending" | "in_progress" | "completed" | "skipped";
  completed_at: string | null;
  notes: string | null;
  order_index: number;
}

// ── Phase 3: Performance ─────────────────────────────────────────────────────

export interface Goal {
  id: number;
  employee_id: number;
  title: string;
  description: string | null;
  type: "individual" | "team" | "company";
  metric_type: "percentage" | "number" | "boolean";
  target_value: number;
  current_value: number;
  due_date: string | null;
  status: "not_started" | "in_progress" | "at_risk" | "achieved" | "missed";
  created_at: string;
  updated_at: string;
}

export interface ReviewCycle {
  id: number;
  name: string;
  type: "annual" | "biannual" | "quarterly" | "probation";
  period_start: string;
  period_end: string;
  status: "setup" | "active" | "closed";
}

export interface Review {
  id: number;
  cycle_id: number;
  employee_id: number;
  reviewer_id: number;
  type: "self" | "manager";
  status: "pending" | "in_progress" | "submitted" | "acknowledged";
  strengths: string | null;
  improvements: string | null;
  overall_comments: string | null;
  rating: number | null;
  submitted_at: string | null;
}

export interface OneOnOne {
  id: number;
  manager_id: number;
  employee_id: number;
  scheduled_at: string;
  agenda: string | null;
  notes: string | null;
  action_items: string; // JSON [{text, done}]
  status: "scheduled" | "completed" | "cancelled";
  created_at: string;
}

// ── Phase 3: Benefits ────────────────────────────────────────────────────────

export interface BenefitPlan {
  id: number;
  name: string;
  category: "medical" | "retirement" | "life" | "disability" | "wellness";
  provider: string | null;
  description: string | null;
  active: number;
}

export interface BenefitTier {
  id: number;
  plan_id: number;
  name: string;
  monthly_cost_employee: number;
  monthly_cost_employer: number;
  description: string | null;
}

export interface BenefitElection {
  id: number;
  employee_id: number;
  tier_id: number;
  status: "active" | "pending" | "ended";
  effective_from: string;
  ended_at: string | null;
}

// ── Phase 3: Expenses ────────────────────────────────────────────────────────

export interface ExpenseCategory {
  id: number;
  name: string;
  code: string;
  monthly_limit: number | null;
  requires_receipt: number;
}

export interface ExpenseClaim {
  id: number;
  employee_id: number;
  category_id: number;
  amount: number;
  expense_date: string;
  description: string;
  receipt_filename: string | null;
  status: "pending" | "approved" | "rejected" | "reimbursed";
  approver_id: number | null;
  decided_at: string | null;
  decision_note: string | null;
  created_at: string;
}
