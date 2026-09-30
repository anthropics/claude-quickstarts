# HR Platform — Sprint Backlog

> Version 1.0 · 2026-06-10  
> Sprint cadence: **2-week sprints**  
> Team: 2 senior full-stack engineers, 1 backend engineer, 1 frontend engineer, 1 mobile engineer, 0.5 designer, 0.5 QA  
> Story points: Fibonacci (1, 2, 3, 5, 8, 13)  
> Capacity per sprint: ~60 points (full team)

---

## Release Roadmap

| Phase | Sprints | Theme | Milestone |
|---|---|---|---|
| 0 | 1–2 | Foundation & Infrastructure | Dev environment ready |
| 1 | 3–8 | Core HR + Leave + Time | MVP Alpha |
| 2 | 9–14 | Payroll + ATS + Onboarding | Beta |
| 3 | 15–20 | Performance + LMS + Benefits + Scheduling | v1.0 |
| 4 | 21–26 | Analytics + Engagement + Compliance + Offboarding | v1.1 |
| 5 | 27–32 | Succession + Compensation + AI + Mobile | v1.2 |
| 6 | 33–36 | Integrations + API + Hardening | GA |

---

## Phase 0 — Foundation

---

### Sprint 1 — Infrastructure & Auth

**Goal:** Dev environment, CI/CD pipeline, auth scaffold, database schema foundation

| # | Story | Points | Module |
|---|---|---|---|
| S1-1 | Set up monorepo (Turborepo): `apps/web`, `apps/api`, `apps/mobile`, `packages/db`, `packages/ui` | 5 | Infra |
| S1-2 | Provision PostgreSQL, Redis, S3-compatible storage in dev/staging | 3 | Infra |
| S1-3 | Configure GitHub Actions CI: lint, type-check, test on PR | 3 | Infra |
| S1-4 | Docker Compose for local dev (all services) | 3 | Infra |
| S1-5 | Integrate Clerk for auth: sign-up, sign-in, session middleware | 5 | Auth |
| S1-6 | RBAC foundation: define roles (Super Admin, Company Admin, HR Manager, Manager, Employee), enforce via middleware | 5 | Auth |
| S1-7 | Multi-tenant schema: `platform` schema + `tenant_<id>` provisioning script | 8 | Infra |
| S1-8 | Base Next.js app shell: layout, navigation sidebar, auth guards, theme (Tailwind + shadcn) | 5 | Web |
| S1-9 | Fastify API scaffold: plugin architecture, request validation (Zod), error handling, OpenTelemetry setup | 5 | API |
| S1-10 | Base DB migration setup (drizzle-orm or Prisma); seed script for demo tenant | 3 | DB |
| S1-11 | Decide Expo managed vs bare workflow; init React Native project | 3 | Mobile |
| S1-12 | ADR: document tech stack decisions | 2 | Docs |

**Sprint total: 50 points**

---

### Sprint 2 — Core Data Models & Dev Tooling

**Goal:** Employee, Company, Department schemas; admin CRUD APIs; design system baseline

| # | Story | Points | Module |
|---|---|---|---|
| S2-1 | Database schema: `employees`, `employment`, `departments`, `companies`, `branches` | 5 | DB |
| S2-2 | Employee list API with filters (name, department, status) + pagination | 3 | Core HR |
| S2-3 | Employee create/update/delete API | 3 | Core HR |
| S2-4 | Company & branch CRUD API | 3 | Core HR |
| S2-5 | Department CRUD API with parent tree structure | 3 | Core HR |
| S2-6 | File upload service: S3 presigned URLs, metadata record, virus scan hook | 5 | Core HR |
| S2-7 | Design system: typography, colour tokens, button/input/card/badge/table components in `packages/ui` | 8 | UI |
| S2-8 | Super Admin web UI: tenant management, create company, user invite | 5 | Admin |
| S2-9 | Custom fields engine: define/store/render custom fields on Employee entity | 8 | Core HR |
| S2-10 | Audit log service: middleware that records every mutation to `audit_log` table | 5 | Compliance |
| S2-11 | Set up Meilisearch; index employees for global search | 3 | Search |

**Sprint total: 51 points**

---

## Phase 1 — Core HR + Leave + Time

---

### Sprint 3 — Employee Profile UI & Org Chart

**Goal:** Full employee profile web UI; org chart visualisation; document vault UI

| # | Story | Points | Module |
|---|---|---|---|
| S3-1 | Employee profile page: personal info tab (view + edit) | 5 | Core HR |
| S3-2 | Employee profile: employment history tab (timeline view) | 3 | Core HR |
| S3-3 | Employee profile: documents tab (upload, preview PDF, download, delete) | 5 | Core HR |
| S3-4 | Employee list page: table with search, filters, pagination, export CSV | 5 | Core HR |
| S3-5 | Add/edit employee form with all fields | 5 | Core HR |
| S3-6 | Org chart page: interactive tree (react-organizational-chart or D3); expand/collapse nodes | 8 | Core HR |
| S3-7 | Org chart: export to PNG/PDF | 3 | Core HR |
| S3-8 | Global search UI: spotlight-style modal, results grouped by type | 5 | Search |
| S3-9 | Role management UI: HR Admin can create roles, assign permissions per module | 5 | Auth |
| S3-10 | HR letter templates: create/edit template with merge fields; preview with sample data | 5 | Core HR |
| S3-11 | HR letter generation: select employee + template → generate PDF | 3 | Core HR |

**Sprint total: 52 points**

---

### Sprint 4 — Leave Management Backend

**Goal:** Leave types, policies, balances, accrual engine, request/approval APIs

| # | Story | Points | Module |
|---|---|---|---|
| S4-1 | DB schema: `leave_types`, `leave_policies`, `leave_requests`, `leave_balances`, `public_holidays` | 5 | Leave |
| S4-2 | Leave type CRUD API (HR Admin only) | 3 | Leave |
| S4-3 | Leave policy CRUD API; assign policy to employee groups | 3 | Leave |
| S4-4 | Leave request submission API (employee) | 3 | Leave |
| S4-5 | Multi-level approval engine: route to approver chain; approve/reject at each level | 8 | Leave |
| S4-6 | Leave balance calculation: entitled − taken − pending | 3 | Leave |
| S4-7 | Accrual engine (BullMQ scheduled job, nightly) | 5 | Leave |
| S4-8 | Carry-over job (annual; applies carry-over rules, respects expiry) | 5 | Leave |
| S4-9 | Public holiday import API; auto-exclude from leave day count | 3 | Leave |
| S4-10 | Probation restriction enforcement on leave request | 2 | Leave |
| S4-11 | Negative balance limit enforcement | 2 | Leave |
| S4-12 | Leave request validation: overlap detection, balance check | 3 | Leave |

**Sprint total: 45 points**

---

### Sprint 5 — Leave Management UI

**Goal:** Employee leave request flow; manager approvals; team calendar; HR leave admin

| # | Story | Points | Module |
|---|---|---|---|
| S5-1 | Employee: leave request form (type, dates, notes, attachment) | 5 | Leave |
| S5-2 | Employee: leave balance cards by leave type | 3 | Leave |
| S5-3 | Employee: my leave history with status badges | 3 | Leave |
| S5-4 | Manager: pending approvals queue with approve/reject + comment | 5 | Leave |
| S5-5 | Manager: team leave calendar (month/week view; colour by leave type) | 8 | Leave |
| S5-6 | HR Admin: leave type configuration UI | 3 | Leave |
| S5-7 | HR Admin: leave policy builder UI | 5 | Leave |
| S5-8 | HR Admin: public holiday management by region | 3 | Leave |
| S5-9 | HR Admin: leave analytics dashboard (utilisation, top types, peak months) | 5 | Leave |
| S5-10 | Email notification: leave request submitted, approved, rejected | 3 | Leave |
| S5-11 | In-app notification: approval request, status change | 3 | Leave |

**Sprint total: 46 points**

---

### Sprint 6 — Time & Attendance Backend

**Goal:** Clock events, geofencing, timesheet engine, overtime rules

| # | Story | Points | Module |
|---|---|---|---|
| S6-1 | DB schema: `clock_events`, `timesheets`, `timesheet_lines`, `geofence_zones`, `overtime_rules` | 5 | Time |
| S6-2 | Clock in/out API (web/mobile); validate against geofence if zone assigned | 5 | Time |
| S6-3 | Break start/end API | 2 | Time |
| S6-4 | Geofence zone management API (HR Admin) | 3 | Time |
| S6-5 | Automatic daily timesheet line generation from clock events | 5 | Time |
| S6-6 | Overtime calculation engine: daily and weekly thresholds, rate multiplier | 8 | Time |
| S6-7 | Timesheet submit / approve / reject API | 3 | Time |
| S6-8 | Late arrival / early departure detection; alert trigger | 3 | Time |
| S6-9 | Attendance summary report API (per employee, per period) | 3 | Time |
| S6-10 | Payroll export: hours summary JSON/CSV for pay period | 3 | Time |
| S6-11 | BullMQ job: daily attendance anomaly check → notification events | 3 | Time |

**Sprint total: 43 points**

---

### Sprint 7 — Time & Attendance UI + Kiosk

**Goal:** Web clock widget; timesheet UI; manager attendance view; kiosk PWA

| # | Story | Points | Module |
|---|---|---|---|
| S7-1 | Employee: clock in/out widget on dashboard (shows current state, elapsed time) | 5 | Time |
| S7-2 | Employee: timesheet view — daily breakdown, edit and submit | 5 | Time |
| S7-3 | Manager: team attendance dashboard — who's in, late, absent today | 5 | Time |
| S7-4 | Manager: pending timesheet approvals | 3 | Time |
| S7-5 | HR Admin: geofence zone management UI (map picker for centre + radius) | 5 | Time |
| S7-6 | HR Admin: overtime rules configuration UI | 3 | Time |
| S7-7 | HR Admin: attendance reports page | 3 | Time |
| S7-8 | Kiosk PWA: fullscreen clock in/out with PIN entry; employee photo confirmation | 8 | Time |
| S7-9 | Alerts UI: late/early departure notification in notification centre | 3 | Time |
| S7-10 | Investigate facial recognition vendor (AWS Rekognition vs in-house); spike | 3 | Time |

**Sprint total: 43 points**

---

### Sprint 8 — Self-Service Portal + Notifications Foundation

**Goal:** Employee self-service portal; notification centre; email/SMS delivery; workflow engine v1

| # | Story | Points | Module |
|---|---|---|---|
| S8-1 | Employee dashboard: leave balance summary, pending tasks, next payslip date, announcements | 5 | SSP |
| S8-2 | Employee: update personal info (with approval gate for sensitive fields) | 3 | SSP |
| S8-3 | Employee: update emergency contacts | 2 | SSP |
| S8-4 | Employee: update banking details (with approval workflow) | 3 | SSP |
| S8-5 | Notification centre UI: bell icon, unread badge, notification list, mark-all-read | 5 | Notifications |
| S8-6 | Notification service: in-app delivery via SSE/WebSocket | 5 | Notifications |
| S8-7 | Email delivery integration (Resend): templated emails with Handlebars | 3 | Notifications |
| S8-8 | SMS delivery integration (Twilio): OTP + transactional SMS | 3 | Notifications |
| S8-9 | Workflow engine v1: trigger → condition → action evaluation; event bus (BullMQ) | 8 | Workflows |
| S8-10 | Built-in workflow rules: leave request triggers (submit, approve, reject) | 3 | Workflows |
| S8-11 | Alpha testing: internal team e2e smoke test; bug bash | 5 | QA |

**Sprint total: 45 points**

---

## Phase 2 — Payroll + ATS + Onboarding

---

### Sprint 9 — Payroll Engine

**Goal:** Core gross-to-net calculation, tax tables, pay run workflow

| # | Story | Points | Module |
|---|---|---|---|
| S9-1 | DB schema: `payroll_runs`, `payslip_lines`, `tax_tables`, `deductions`, `earnings_codes` | 5 | Payroll |
| S9-2 | Earnings and deductions configuration API (HR Admin) | 3 | Payroll |
| S9-3 | Tax table management API + seed tables for SA, UK, US | 5 | Payroll |
| S9-4 | Gross-to-net calculation engine (sync function, testable in isolation) | 13 | Payroll |
| S9-5 | Pay run create / process / approve / pay workflow API | 5 | Payroll |
| S9-6 | Payslip PDF generation (React PDF or Puppeteer) | 5 | Payroll |
| S9-7 | Payslip email distribution to employees | 3 | Payroll |
| S9-8 | Payroll audit trail API: log every change to a pay run | 3 | Payroll |
| S9-9 | Bank file export: EFT (SA), BACS (UK), NACHA (US) formats | 5 | Payroll |

**Sprint total: 47 points**

---

### Sprint 10 — Payroll UI + Multi-currency

**Goal:** Payroll admin UI; payslip self-service; multi-currency support

| # | Story | Points | Module |
|---|---|---|---|
| S10-1 | Payroll admin: pay run list (history + current) | 3 | Payroll |
| S10-2 | Payroll admin: create / configure pay run | 5 | Payroll |
| S10-3 | Payroll admin: employee pay run review — line-by-line drill-down | 5 | Payroll |
| S10-4 | Payroll admin: approve and mark as paid | 3 | Payroll |
| S10-5 | Payroll admin: earnings & deductions configuration UI | 5 | Payroll |
| S10-6 | Payroll admin: bank file download | 2 | Payroll |
| S10-7 | Employee: payslip history; PDF download | 3 | Payroll |
| S10-8 | Multi-currency: currency selection per company; exchange rate management | 5 | Payroll |
| S10-9 | Bonus & incentive processing: ad-hoc payment UI + API | 5 | Payroll |
| S10-10 | Payroll compliance reports: IRP5 (SA) report generation | 8 | Payroll |
| S10-11 | Integration stub for accounting export (Xero/QuickBooks journal format) | 3 | Payroll |

**Sprint total: 47 points**

---

### Sprint 11 — ATS Backend

**Goal:** Job posting, candidate, application, pipeline APIs; AI screening

| # | Story | Points | Module |
|---|---|---|---|
| S11-1 | DB schema: `job_postings`, `candidates`, `applications`, `interviews`, `offers` | 5 | ATS |
| S11-2 | Job posting CRUD API (draft → open → closed lifecycle) | 3 | ATS |
| S11-3 | Public careers page API (no auth; returns open postings by tenant slug) | 3 | ATS |
| S11-4 | Application submission API: upload CV, capture candidate info | 5 | ATS |
| S11-5 | CV parsing service: extract name/email/phone/experience/skills from PDF/DOCX | 8 | ATS |
| S11-6 | AI screening: Claude API call with JD + CV content; returns score + summary; store result | 8 | ATS |
| S11-7 | Stage transition API (advance/reject/withdraw) | 3 | ATS |
| S11-8 | Interview scheduling API: create interview record; calendar invite generation | 5 | ATS |
| S11-9 | Interview feedback API: submit scorecard | 3 | ATS |
| S11-10 | Offer letter generation API: template + merge fields + PDF | 5 | ATS |
| S11-11 | Candidate communication: send templated email/SMS to candidate(s) | 3 | ATS |

**Sprint total: 51 points**

---

### Sprint 12 — ATS UI

**Goal:** Recruiter and hiring manager UI; pipeline board; analytics

| # | Story | Points | Module |
|---|---|---|---|
| S12-1 | Job postings list + create/edit form | 5 | ATS |
| S12-2 | Kanban pipeline board: columns per stage; drag card to advance; bulk actions | 8 | ATS |
| S12-3 | Candidate profile page: CV preview, AI screening score, timeline, notes | 5 | ATS |
| S12-4 | Interview scheduling UI: date/time picker, interviewer multi-select, candidate notify | 5 | ATS |
| S12-5 | Interview feedback form (scorecard per competency + overall rating) | 3 | ATS |
| S12-6 | Offer creation UI: enter terms, generate letter, send to candidate | 5 | ATS |
| S12-7 | Candidate comms UI: template selector, preview, send | 3 | ATS |
| S12-8 | Recruitment analytics page: time-to-hire funnel, source breakdown, open roles ageing | 5 | ATS |
| S12-9 | Public careers page (embeddable widget + standalone page) | 5 | ATS |
| S12-10 | Hired → create employee flow: pre-fill employee profile from candidate data | 5 | ATS |

**Sprint total: 49 points**

---

### Sprint 13 — Onboarding

**Goal:** Onboarding checklists, document collection, task management, new hire portal

| # | Story | Points | Module |
|---|---|---|---|
| S13-1 | DB schema: `onboarding_templates`, `onboarding_tasks`, `task_assignments` | 3 | Onboarding |
| S13-2 | Onboarding template builder: drag-and-drop checklist; assignee type (HR/IT/Manager/New Hire) | 8 | Onboarding |
| S13-3 | Onboarding workflow trigger: on employment created, instantiate template as task list | 5 | Onboarding |
| S13-4 | Welcome email automation: configurable trigger `N days before start_date` | 3 | Onboarding |
| S13-5 | Document collection task: new hire uploads document; HR marks complete | 5 | Onboarding |
| S13-6 | E-signature integration (DocuSign): send contract for signing; webhook on completion | 8 | Onboarding |
| S13-7 | Equipment/IT access request tasks: auto-create for IT team; status tracking | 5 | Onboarding |
| S13-8 | Buddy assignment: HR assigns buddy; buddy receives checklist | 3 | Onboarding |
| S13-9 | HR dashboard: onboarding progress per new hire; overdue task alerts | 5 | Onboarding |
| S13-10 | New hire self-service: restricted pre-boarding view → full access on start date | 3 | Onboarding |
| S13-11 | Probation tracking: countdown on employee profile; reminder notifications | 3 | Onboarding |

**Sprint total: 51 points**

---

### Sprint 14 — Offboarding + Phase 2 QA

**Goal:** Offboarding workflows; exit interview; asset checklist; Phase 2 regression testing

| # | Story | Points | Module |
|---|---|---|---|
| S14-1 | DB schema: `offboarding_cases`, `exit_interviews`, `asset_checklists` | 3 | Offboarding |
| S14-2 | Resignation self-service: employee submits resignation with notice period | 5 | Offboarding |
| S14-3 | Termination initiation by HR: reason, last working day, type | 3 | Offboarding |
| S14-4 | Offboarding task checklist (mirror of onboarding engine, re-used) | 5 | Offboarding |
| S14-5 | IT access revocation task: auto-created; escalation if not complete by exit date | 5 | Offboarding |
| S14-6 | Exit interview: schedule, digital form, submission, HR view | 5 | Offboarding |
| S14-7 | Asset return checklist: item-by-item sign-off; export to PDF | 3 | Offboarding |
| S14-8 | Final payroll trigger: API call to payroll with leave payout amount | 3 | Offboarding |
| S14-9 | Employee status → terminated; archive profile; retain audit log | 3 | Offboarding |
| S14-10 | Rehire eligibility flag (HR sets eligible/ineligible with notes) | 2 | Offboarding |
| S14-11 | Phase 2 regression testing; fix critical bugs; update API docs | 5 | QA |

**Sprint total: 42 points**

---

## Phase 3 — Performance + LMS + Benefits + Scheduling

---

### Sprint 15 — Performance Management Backend

| # | Story | Points | Module |
|---|---|---|---|
| S15-1 | DB schema: `review_cycles`, `review_forms`, `goals`, `one_on_ones`, `pips` | 5 | Performance |
| S15-2 | Review cycle CRUD + lifecycle (setup → active → closed) | 3 | Performance |
| S15-3 | Review template builder: sections, question types, rating scales | 8 | Performance |
| S15-4 | Review form generation for cycle: create form per employee × reviewer pairing | 5 | Performance |
| S15-5 | Self-assessment submission API | 3 | Performance |
| S15-6 | Manager assessment submission API | 3 | Performance |
| S15-7 | 360 peer nomination and feedback collection API | 5 | Performance |
| S15-8 | Goal CRUD API: individual/team/company, OKR key results, progress updates | 5 | Performance |
| S15-9 | 1-on-1 scheduling API + agenda/notes storage | 3 | Performance |
| S15-10 | PIP creation and check-in workflow API | 5 | Performance |
| S15-11 | Automated cycle reminders (BullMQ scheduled) | 3 | Performance |

**Sprint total: 48 points**

---

### Sprint 16 — Performance Management UI

| # | Story | Points | Module |
|---|---|---|---|
| S16-1 | HR Admin: review cycle management (create, launch, close) | 5 | Performance |
| S16-2 | HR Admin: review template builder UI | 8 | Performance |
| S16-3 | Employee: self-assessment form | 5 | Performance |
| S16-4 | Manager: team review queue + assessment form | 5 | Performance |
| S16-5 | 360 peer feedback: nomination UI + anonymous submission form | 5 | Performance |
| S16-6 | Goals: create/edit/update progress; OKR cascading view | 5 | Performance |
| S16-7 | 1-on-1 meeting UI: agenda builder, notes editor, action items, history | 5 | Performance |
| S16-8 | PIP management UI (HR + Manager) | 5 | Performance |
| S16-9 | Performance dashboard: rating distribution, 9-box teaser (v1) | 5 | Performance |
| S16-10 | Skill gap analysis: employee rating vs role benchmark table | 3 | Performance |

**Sprint total: 51 points**

---

### Sprint 17 — LMS

| # | Story | Points | Module |
|---|---|---|---|
| S17-1 | DB schema: `courses`, `lessons`, `learning_paths`, `enrolments`, `quiz_attempts`, `certifications` | 5 | LMS |
| S17-2 | Course builder: create course, add sections & lessons (video/PDF/article) | 8 | LMS |
| S17-3 | Video upload + S3 storage + streaming (signed URL playback) | 5 | LMS |
| S17-4 | Quiz builder: question bank, pass threshold, retry logic | 5 | LMS |
| S17-5 | Self-enrolment & assigned enrolment APIs | 3 | LMS |
| S17-6 | Learning path builder: ordered course sequence; auto-enrol by role | 5 | LMS |
| S17-7 | Course player UI: lesson navigation, progress tracking, resume | 8 | LMS |
| S17-8 | Quiz taking UI + result screen + certificate generation | 5 | LMS |
| S17-9 | Certification expiry alert (BullMQ scheduled, 60/30/7 days prior) | 3 | LMS |
| S17-10 | HR Admin: training completion reports | 3 | LMS |
| S17-11 | SCORM 1.2 import spike / basic support | 5 | LMS |

**Sprint total: 55 points**

---

### Sprint 18 — Benefits Administration

| # | Story | Points | Module |
|---|---|---|---|
| S18-1 | DB schema: `benefit_plans`, `benefit_tiers`, `employee_benefit_elections`, `open_enrolment_windows` | 5 | Benefits |
| S18-2 | Benefit plan CRUD API (HR Admin) | 3 | Benefits |
| S18-3 | Benefit tier + cost table management API | 3 | Benefits |
| S18-4 | Employee self-enrolment API | 3 | Benefits |
| S18-5 | Open enrolment window management (start/end date, lock after deadline) | 5 | Benefits |
| S18-6 | Life event re-enrolment trigger | 3 | Benefits |
| S18-7 | Benefits admin UI: plan setup, tier management, enrolment overview | 5 | Benefits |
| S18-8 | Employee: benefits selection UI (enrolment portal) | 5 | Benefits |
| S18-9 | Benefits cost report: employer vs employee contributions | 5 | Benefits |
| S18-10 | Total compensation statement PDF generation (base + benefits + bonus) | 5 | Benefits |

**Sprint total: 42 points**

---

### Sprint 19 — Shift Scheduling

| # | Story | Points | Module |
|---|---|---|---|
| S19-1 | DB schema: `shifts`, `shift_templates`, `employee_availability`, `shift_swap_requests` | 5 | Scheduling |
| S19-2 | Shift CRUD API | 3 | Scheduling |
| S19-3 | Drag-and-drop schedule builder UI (react-big-calendar or custom; week view) | 13 | Scheduling |
| S19-4 | Shift template save/apply | 3 | Scheduling |
| S19-5 | Availability management: employee submits recurring/one-off unavailability | 5 | Scheduling |
| S19-6 | Shift swap request: propose + approve flow | 5 | Scheduling |
| S19-7 | Overtime and coverage gap alerts (validate on publish) | 3 | Scheduling |
| S19-8 | Shift publish: notify affected employees (push + email) | 3 | Scheduling |
| S19-9 | Roster export: PDF/CSV | 3 | Scheduling |

**Sprint total: 43 points**

---

### Sprint 20 — Expense Management + Phase 3 QA

| # | Story | Points | Module |
|---|---|---|---|
| S20-1 | DB schema: `expenses`, `expense_claims`, `expense_categories`, `per_diem_policies` | 3 | Expense |
| S20-2 | Expense claim submission API: receipt upload, OCR extraction (AWS Textract or Google Vision) | 8 | Expense |
| S20-3 | Expense approval workflow (shared approval engine from Leave module) | 3 | Expense |
| S20-4 | Per diem / policy limit management API | 3 | Expense |
| S20-5 | Payroll-linked reimbursement export | 3 | Expense |
| S20-6 | Expense UI: submission form with camera/upload, claim list, status | 5 | Expense |
| S20-7 | Expense UI: manager approval queue | 3 | Expense |
| S20-8 | Expense reports: spend by category/department/employee | 3 | Expense |
| S20-9 | Phase 3 regression testing and bug bash; performance profiling | 5 | QA |
| S20-10 | Update API docs and OpenAPI spec through current sprint | 3 | Docs |

**Sprint total: 39 points**

---

## Phase 4 — Analytics + Engagement + Compliance + Offboarding Polish

---

### Sprint 21 — HR Analytics & Reporting

| # | Story | Points | Module |
|---|---|---|---|
| S21-1 | Reporting data warehouse: materialised views / read replica for heavy queries | 8 | Analytics |
| S21-2 | Pre-built reports: headcount, turnover, absenteeism, payroll cost (API + UI) | 8 | Analytics |
| S21-3 | Custom report builder: drag-and-drop columns, filters, grouping, chart types | 13 | Analytics |
| S21-4 | Diversity & inclusion dashboard: gender/age/ethnicity breakdowns | 5 | Analytics |
| S21-5 | Data export: CSV, Excel (xlsx), PDF for any report | 3 | Analytics |
| S21-6 | Scheduled report delivery: cron schedule + email recipient list | 5 | Analytics |

**Sprint total: 42 points**

---

### Sprint 22 — Employee Engagement & Wellness

| # | Story | Points | Module |
|---|---|---|---|
| S22-1 | DB schema: `surveys`, `survey_questions`, `survey_responses`, `recognitions`, `announcements` | 5 | Engagement |
| S22-2 | Survey builder: question types (rating, NPS, multiple choice, open text) | 8 | Engagement |
| S22-3 | Survey assignment, reminder, and response collection | 5 | Engagement |
| S22-4 | eNPS calculation and trend chart | 3 | Engagement |
| S22-5 | Anonymous feedback: strip identifiers before HR view | 3 | Engagement |
| S22-6 | Peer recognition: nominate + message; approval optional; newsfeed display | 5 | Engagement |
| S22-7 | Milestone celebrations: auto-post birthday/work anniversary to newsfeed | 3 | Engagement |
| S22-8 | Company newsfeed/announcements: HR posts; employees see on dashboard | 5 | Engagement |
| S22-9 | Burnout alert: AI-assisted flag for employees with 90+ days no leave or chronic overtime | 5 | Engagement |
| S22-10 | Wellness programs: link + participation tracking | 3 | Engagement |

**Sprint total: 45 points**

---

### Sprint 23 — Compliance & Legal

| # | Story | Points | Module |
|---|---|---|---|
| S23-1 | Labour law compliance checklist (HR marks obligations complete; by country) | 5 | Compliance |
| S23-2 | SA statutory reports: UIF, SDL, COIDA, EEA2/EEA4 generation | 8 | Compliance |
| S23-3 | POPIA/GDPR: data subject request portal (access, correction, deletion) | 8 | Compliance |
| S23-4 | Data retention automation: BullMQ job deletes/anonymises records past retention window | 5 | Compliance |
| S23-5 | Disciplinary case management: incident → hearing → outcome; case file | 8 | Compliance |
| S23-6 | Grievance tracking: submission, investigation assignment, outcome, appeal | 5 | Compliance |
| S23-7 | Contract expiry alerts (30/14/7-day notifications) | 3 | Compliance |
| S23-8 | Audit log UI: searchable, filterable, exportable | 5 | Compliance |

**Sprint total: 47 points**

---

### Sprint 24 — Workflow Automation Builder

| # | Story | Points | Module |
|---|---|---|---|
| S24-1 | Visual workflow builder UI: drag-and-drop trigger → condition → action canvas | 13 | Workflows |
| S24-2 | Trigger catalogue: all HR events exposed as trigger options | 5 | Workflows |
| S24-3 | Condition builder: field comparisons, boolean logic | 5 | Workflows |
| S24-4 | Action catalogue: email, SMS, in-app, create task, update field, call webhook | 5 | Workflows |
| S24-5 | Approval routing rules: dynamic approver by manager chain / named person | 5 | Workflows |
| S24-6 | Escalation rules: stalled approval auto-escalates after N hours | 3 | Workflows |
| S24-7 | Workflow run history + debug log | 3 | Workflows |
| S24-8 | Outbound webhook delivery: HMAC-signed payload; retry with backoff; delivery log | 5 | Workflows |

**Sprint total: 44 points**

---

## Phase 5 — Succession + Compensation + AI + Mobile

---

### Sprint 25 — Succession Planning & Talent Management

| # | Story | Points | Module |
|---|---|---|---|
| S25-1 | DB schema: `talent_pools`, `career_paths`, `succession_plans`, `competency_matrix` | 5 | Succession |
| S25-2 | Talent pool management: tag employees as hi-po; group by level/function | 5 | Succession |
| S25-3 | 9-box grid (performance × potential): interactive; data from review cycle | 8 | Succession |
| S25-4 | Career path mapping: define role progressions; employee self-nominates interest | 5 | Succession |
| S25-5 | Succession readiness scoring: HR/manager sets 1–3 scale per role | 3 | Succession |
| S25-6 | Leadership pipeline dashboard: bench depth by level | 5 | Succession |
| S25-7 | Skills & competency matrix: role benchmark vs actual heatmap | 5 | Succession |
| S25-8 | Internal job board: post role internally first; ATS tracks internal applicants | 5 | Succession |

**Sprint total: 41 points**

---

### Sprint 26 — Compensation Management

| # | Story | Points | Module |
|---|---|---|---|
| S26-1 | DB schema: `salary_grades`, `salary_bands`, `merit_cycles`, `compensation_proposals` | 5 | Compensation |
| S26-2 | Salary grade/band management API + UI | 5 | Compensation |
| S26-3 | Pay equity analysis: statistical comparison within grade by demographic | 8 | Compensation |
| S26-4 | Merit increase workflow: upload budget → managers propose → HR approves | 8 | Compensation |
| S26-5 | Bonus & incentive planning: target % by grade; payout from performance score | 5 | Compensation |
| S26-6 | Compensation approval chain (configurable; above-threshold goes to CFO) | 5 | Compensation |
| S26-7 | Total compensation statement PDF (base + benefits + bonus + equity placeholder) | 5 | Compensation |
| S26-8 | Industry benchmarking: manual upload of market data file; compare vs bands | 5 | Compensation |

**Sprint total: 46 points**

---

### Sprint 27 — AI Features

| # | Story | Points | Module |
|---|---|---|---|
| S27-1 | HR chatbot: Claude API with RAG over company documents (policies, procedures); chat UI | 13 | AI |
| S27-2 | Predictive attrition: monthly BullMQ job; Claude scores flight risk; HR alert dashboard | 8 | AI |
| S27-3 | Anomaly detection: attendance/leave/expense anomalies → HR alert | 5 | AI |
| S27-4 | Smart report generation: natural language query → generated SQL → rendered report | 8 | AI |
| S27-5 | Performance insights: Claude analyses review data → coaching suggestions for managers | 5 | AI |
| S27-6 | AI prompts admin UI: HR Admin can edit screening/chatbot prompts; view AI call log | 5 | AI |

**Sprint total: 44 points**

---

### Sprint 28 — Mobile App (Core Features)

| # | Story | Points | Module |
|---|---|---|---|
| S28-1 | Mobile app shell: navigation, auth (Clerk SDK), biometric unlock | 5 | Mobile |
| S28-2 | Mobile: dashboard — tasks, leave balance, announcements | 5 | Mobile |
| S28-3 | Mobile: leave request + approval (full parity with web) | 8 | Mobile |
| S28-4 | Mobile: clock in/out with GPS location capture + geofence enforcement | 8 | Mobile |
| S28-5 | Mobile: payslip list + PDF viewer | 3 | Mobile |
| S28-6 | Mobile: push notifications (FCM + APNs via Expo) | 5 | Mobile |
| S28-7 | Mobile: team calendar (read-only) | 3 | Mobile |
| S28-8 | Mobile: expense claim with camera receipt capture | 5 | Mobile |
| S28-9 | Mobile: offline mode for timesheet (local SQLite cache; sync on reconnect) | 8 | Mobile |

**Sprint total: 50 points**

---

## Phase 6 — Integrations + API + Hardening

---

### Sprint 29 — Public API & Webhooks

| # | Story | Points | Module |
|---|---|---|---|
| S29-1 | OAuth 2.0: client credentials + authorization code flows | 8 | API |
| S29-2 | API key management UI (HR Admin creates/revokes keys) | 3 | API |
| S29-3 | Rate limiting per tenant (1,000 req/min); 429 responses with Retry-After | 3 | API |
| S29-4 | OpenAPI 3.1 spec generation (auto-generated from route schemas) + Swagger UI at `/api/docs` | 5 | API |
| S29-5 | Webhook subscription management: HR Admin registers URL + event types | 5 | API |
| S29-6 | HMAC-signed webhook delivery with retry + dead-letter queue | 5 | API |
| S29-7 | Webhook delivery log UI | 3 | API |
| S29-8 | Zapier connector: publish trigger/action app using webhook infrastructure | 8 | API |

**Sprint total: 40 points**

---

### Sprint 30 — Slack & Teams Integration

| # | Story | Points | Module |
|---|---|---|---|
| S30-1 | Slack app: OAuth install flow per tenant | 5 | Integrations |
| S30-2 | Slack: leave approval actions in notification message (approve/reject buttons) | 8 | Integrations |
| S30-3 | Slack: HR chatbot slash command (`/hr ask <question>`) | 8 | Integrations |
| S30-4 | Slack: company announcement publishing | 3 | Integrations |
| S30-5 | MS Teams app: OAuth install flow per tenant | 5 | Integrations |
| S30-6 | MS Teams: Adaptive Card for leave approvals | 8 | Integrations |
| S30-7 | MS Teams: HR chatbot bot integration | 5 | Integrations |

**Sprint total: 42 points**

---

### Sprint 31 — Calendar, SSO, Accounting Integrations

| # | Story | Points | Module |
|---|---|---|---|
| S31-1 | Google Calendar sync: leave + interview events | 5 | Integrations |
| S31-2 | Outlook/Exchange Calendar sync | 5 | Integrations |
| S31-3 | Google Workspace Directory sync: import employees from Google Directory | 5 | Integrations |
| S31-4 | SAML 2.0 SSO: SP-initiated flow; Okta + Azure AD tested | 8 | Auth |
| S31-5 | OIDC SSO: Google + Microsoft | 5 | Auth |
| S31-6 | Xero payroll journal export: OAuth + journal POST | 5 | Integrations |
| S31-7 | QuickBooks payroll journal export | 5 | Integrations |
| S31-8 | LinkedIn job board publish: Jobs API integration | 5 | Integrations |

**Sprint total: 43 points**

---

### Sprint 32 — DocuSign, Job Boards, Performance & Security

| # | Story | Points | Module |
|---|---|---|---|
| S32-1 | DocuSign: send envelope, webhook on sign completion, store signed doc | 8 | Integrations |
| S32-2 | Indeed job board posting integration | 5 | Integrations |
| S32-3 | Workforce demand forecasting (ML model: headcount trend + leading indicators) | 8 | Analytics |
| S32-4 | Security hardening: OWASP checklist pass; CSP headers; SQL injection audit | 8 | Security |
| S32-5 | Penetration test remediation (external pen test results) | 5 | Security |
| S32-6 | Field-level encryption for ID numbers and banking details | 5 | Security |
| S32-7 | Performance profiling: identify and fix API endpoints > 200ms p95 | 5 | Performance |

**Sprint total: 44 points**

---

### Sprint 33 — Accessibility, i18n, Mobile Polish

| # | Story | Points | Module |
|---|---|---|---|
| S33-1 | WCAG 2.1 AA audit (web) — automated + manual; fix critical gaps | 8 | Accessibility |
| S33-2 | Keyboard navigation audit and fixes | 5 | Accessibility |
| S33-3 | Screen reader testing (NVDA/VoiceOver); fix ARIA issues | 5 | Accessibility |
| S33-4 | i18n: extract all strings to translation files (en-ZA, en-GB, en-US) | 8 | i18n |
| S33-5 | Afrikaans (af-ZA) translation | 5 | i18n |
| S33-6 | Date/time/number formatting per locale | 3 | i18n |
| S33-7 | Mobile: iOS + Android app store submission preparation | 5 | Mobile |
| S33-8 | Mobile: E2E tests (Detox) for critical flows | 5 | Mobile |

**Sprint total: 44 points**

---

### Sprint 34 — Launch Readiness

| # | Story | Points | Module |
|---|---|---|---|
| S34-1 | Full E2E test suite (Playwright): all critical user journeys | 8 | QA |
| S34-2 | Load testing (k6): 1,000 concurrent users; payroll run benchmark | 5 | Performance |
| S34-3 | Disaster recovery drill: simulate DB failure; validate RTO < 4h | 5 | Infra |
| S34-4 | SOC 2 Type II readiness: evidence collection, policy docs | 5 | Security |
| S34-5 | Data migration tooling: import from common systems (BambooHR CSV, Sage CSV) | 5 | Infra |
| S34-6 | In-app onboarding tours (new tenant wizard, module onboarding tooltips) | 5 | UX |
| S34-7 | Help centre content: 50 articles covering core modules | 5 | Docs |
| S34-8 | Production infrastructure: Kubernetes cluster, monitoring (Grafana), alerting (PagerDuty) | 8 | Infra |
| S34-9 | Final bug bash + go/no-go sign-off | 3 | QA |

**Sprint total: 49 points**

---

## Summary

| Phase | Sprints | Total Points | Key Deliverables |
|---|---|---|---|
| 0 — Foundation | 1–2 | ~101 | Infra, auth, data models, design system |
| 1 — Core HR + Leave + Time | 3–8 | ~269 | Employee profiles, leave, time, SSP, notifications |
| 2 — Payroll + ATS + Onboarding | 9–14 | ~287 | Payroll, recruitment, onboarding, offboarding |
| 3 — Performance + LMS + Benefits + Scheduling | 15–20 | ~279 | Performance reviews, LMS, benefits, shifts, expenses |
| 4 — Analytics + Engagement + Compliance | 21–24 | ~178 | Reporting, surveys, compliance, workflow builder |
| 5 — Succession + Compensation + AI + Mobile | 25–28 | ~181 | Succession, compensation, AI features, mobile app |
| 6 — Integrations + API + Hardening | 29–34 | ~262 | Public API, Slack/Teams, SSO, security, GA launch |
| **Total** | **34 sprints (~17 months)** | **~1,557** | **All 22 modules live** |

---

## Backlog Grooming Notes

- **Priorities are fixed within a phase** but can be reordered across phases based on customer feedback.
- **Dependencies:** Payroll (Sprint 9) requires Time module (Sprint 6) for hours export; Succession (Sprint 25) requires Performance (Sprint 15–16) for 9-box data; AI (Sprint 27) requires all data modules to be live.
- **Scope risk:** Payroll tax engine complexity (Sprint 9) is the highest-risk item — consider licensing a tax engine if Sprint 9 velocity falls below 40 points.
- **Quick wins for demo/pilot:** After Sprint 8 (Phase 1 complete), a pilot customer can use Core HR + Leave + Time + Self-Service. Pitch this as the Alpha release milestone.
