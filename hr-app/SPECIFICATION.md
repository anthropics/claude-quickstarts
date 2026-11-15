# HR Platform — Product Specification

> Version 1.0 · 2026-06-10

---

## 1. Overview

A full-suite, cloud-native Human Resources platform covering the entire employee lifecycle — from recruitment through offboarding — with AI-assisted decision support, mobile access, and open integration APIs.

**Codename:** HRCore  
**Target market:** Mid-market to enterprise (50–5,000 employees), multi-branch, multi-country  
**Deployment:** SaaS (cloud-hosted), with optional on-premise export

---

## 2. Goals & Success Metrics

| Goal | KPI |
|---|---|
| Reduce manual HR admin time | ≥40% reduction in time-on-task within 6 months |
| Unified employee record | Single source of truth — zero data duplication across modules |
| Compliance | 100% of statutory reports generated without manual intervention |
| Adoption | ≥80% of employees actively using self-service portal within 3 months of go-live |
| Time-to-hire | ≥20% reduction measured across ATS module |

---

## 3. Architecture

### 3.1 Tech Stack

| Layer | Technology |
|---|---|
| Frontend (web) | Next.js 15, TypeScript, Tailwind CSS, shadcn/ui |
| Mobile | React Native (Expo), iOS + Android |
| Backend API | Node.js + TypeScript, Fastify framework |
| Auth | Clerk (SSO/SAML/OIDC) |
| Database | PostgreSQL 16 (primary), Redis 7 (cache + queues) |
| File storage | S3-compatible (AWS S3 / Cloudflare R2) |
| Search | Meilisearch |
| Background jobs | BullMQ |
| Email / SMS | Resend (email), Twilio (SMS) |
| AI | Anthropic Claude API (claude-fable-5 for complex reasoning, claude-haiku-4-5 for high-volume tasks) |
| E-signature | DocuSign API (or Dropbox Sign) |
| Observability | OpenTelemetry → Grafana stack |
| CI/CD | GitHub Actions, Docker, Kubernetes |

### 3.2 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Clients                                  │
│   Next.js Web App        React Native App       API consumers   │
└────────────┬──────────────────────┬──────────────────┬──────────┘
             │                      │                  │
             ▼                      ▼                  ▼
┌────────────────────────────────────────────────────────────────┐
│                    API Gateway / Edge (CDN)                     │
│           Rate limiting · Auth middleware · CORS               │
└────────────────────────────┬───────────────────────────────────┘
                             │
        ┌────────────────────┼──────────────────────┐
        ▼                    ▼                       ▼
┌──────────────┐   ┌──────────────────┐   ┌─────────────────┐
│  Core API    │   │  Webhook/Events  │   │  AI Service     │
│  (Fastify)   │   │  (BullMQ)        │   │  (Claude API)   │
└──────┬───────┘   └──────────────────┘   └─────────────────┘
       │
  ┌────┴─────┐
  │ Services │  (one per domain module — see §4)
  └────┬─────┘
       │
┌──────┴──────────────────────────────────────────┐
│  Data Layer                                      │
│  PostgreSQL (primary)   Redis   S3 / R2          │
└──────────────────────────────────────────────────┘
```

### 3.3 Data Tenancy

Multi-tenant with schema-per-tenant isolation in PostgreSQL. A central `platform` schema holds tenant registry and billing. Each tenant gets its own `tenant_<id>` schema. Row-level security (RLS) enforced at the database level as a secondary guard.

### 3.4 Role-Based Access Control (RBAC)

| Role | Scope |
|---|---|
| Super Admin | Platform-level — manages tenants |
| Company Admin | All modules within one company |
| HR Manager | Full HR access, no billing |
| Department Manager | Own department's employees only |
| Employee | Own records via self-service portal |
| Recruiter | ATS module only |
| Finance | Payroll & expense modules |
| Read Only | Audit/reporting access |

Custom roles with granular permissions per module are supported.

---

## 4. Module Specifications

---

### Module 1 — Core HR / Employee Database

**Purpose:** Master record for all employee data. Every other module links back here.

#### Data Model (key entities)

```
Employee
  id, tenant_id, employee_number, first_name, last_name, preferred_name
  date_of_birth, gender, nationality, id_number, passport_number
  personal_email, work_email, phone
  profile_photo_url
  status: active | on_leave | terminated | suspended
  created_at, updated_at

Employment
  id, employee_id, company_id, branch_id, department_id
  job_title, job_level, employment_type: full_time | part_time | contract | intern
  start_date, end_date, probation_end_date
  manager_id (→ Employee), cost_centre
  contract_type, notice_period_days

Department
  id, tenant_id, name, parent_department_id (tree), head_employee_id

Company / Branch
  id, tenant_id, name, registration_number, tax_number
  address, country, timezone, currency
```

#### Features

- **Employee profile CRUD** — all personal, employment, and banking fields
- **Employment history timeline** — each role change is a versioned record
- **Org chart** — interactive tree built from `manager_id` hierarchy; export to PNG/PDF
- **Document vault** — upload, tag, version-control files; virus scan on upload; configurable retention policy
- **Custom fields** — HR Admin can define text/date/dropdown/boolean fields on any entity without a deployment
- **Custom forms** — drag-and-drop form builder; forms can be assigned to onboarding workflows or standalone
- **HR letter generation** — template engine (Handlebars) with merge fields; appointment, confirmation, warning, salary increase letter types; PDF output; e-signature integration
- **Multi-company/multi-branch** — single login, switch between entities; consolidated and per-entity reporting
- **Separation management** — captures reason, exit date, final settlement trigger; links to offboarding workflow

#### API surface (examples)

```
GET    /employees                  list with filters & pagination
POST   /employees                  create employee
GET    /employees/:id              full profile
PATCH  /employees/:id              partial update
GET    /employees/:id/history      employment timeline
GET    /org-chart/:dept_id         tree data
POST   /documents/upload           presigned S3 URL + metadata record
GET    /employees/:id/documents    list docs for employee
POST   /letters/generate           generate letter PDF from template
```

---

### Module 2 — Leave & Absence Management

#### Data Model

```
LeaveType
  id, tenant_id, name, code, colour
  paid: boolean, requires_approval: boolean
  accrual_method: manual | monthly | annually | per_pay_period
  accrual_rate, max_balance, carry_over_days, carry_over_expiry_months
  negative_balance_allowed, max_negative_days
  gender_restricted (maternity/paternity), probation_restricted

LeavePolicy
  id, tenant_id, name
  leave_type_id, applicable_to (employee_group / department / all)

LeaveRequest
  id, employee_id, leave_type_id
  start_date, end_date, days_requested
  status: pending | approved | rejected | cancelled
  notes, attachment_url
  approver_chain: JSONB (ordered list of approver_ids + statuses)

LeaveBalance
  id, employee_id, leave_type_id, year
  entitled, taken, pending, carried_over, balance

PublicHoliday
  id, tenant_id, name, date, region_code
```

#### Features

- Multi-level approval chains (up to 5 levels); parallel or sequential
- Accrual engine runs nightly via scheduled BullMQ job
- Carry-over processing job on Jan 1 (or custom year-end date)
- Team leave calendar — visual month/week view showing who is out
- Probation restriction — leave type flagged as restricted blocks requests until `probation_end_date`
- Negative balance — configurable per leave type; alerts at threshold
- Public holiday management — import by country/region; auto-excluded from leave day counts
- Mobile leave request — push notification to approvers
- Analytics dashboard — utilisation rates, top leave types, peak periods

---

### Module 3 — Time & Attendance

#### Data Model

```
ClockEvent
  id, employee_id, type: clock_in | clock_out | break_start | break_end
  timestamp, method: web | mobile | kiosk | biometric
  location: POINT (lat/lng), ip_address, device_id
  photo_url (facial recognition capture)

Timesheet
  id, employee_id, period_start, period_end
  status: draft | submitted | approved | rejected
  total_hours, regular_hours, overtime_hours

TimesheetLine
  id, timesheet_id, date, start_time, end_time
  break_minutes, total_minutes, notes

GeofenceZone
  id, tenant_id, name, centre: POINT, radius_metres
  allowed_for (employee_group / all)

OvertimeRule
  id, tenant_id, name
  daily_threshold_hours, weekly_threshold_hours
  rate_multiplier (e.g. 1.5 for time-and-a-half)
```

#### Features

- Web, mobile and kiosk clock-in (kiosk = PWA on tablet)
- GPS geofencing — clock-in blocked outside authorised zones; configurable per employee group
- Facial recognition — optional; liveness detection; falls back to PIN on failure
- Automatic overtime calculation using configured rules
- Late/early departure alerts — push + email notification to manager
- Timesheet submission + multi-level approval
- Payroll export — generate hours summary in CSV/JSON for payroll import
- Real-time attendance dashboard — live view of who is in/out

---

### Module 4 — Payroll Management

#### Data Model

```
PayrollRun
  id, tenant_id, period_start, period_end, payment_date
  status: draft | processing | approved | paid | cancelled
  currency, exchange_rate

PayslipLine
  id, payroll_run_id, employee_id
  gross_pay, net_pay, employer_cost
  lines: JSONB (earnings + deductions itemised)

TaxTable
  id, tenant_id, country_code, tax_year
  brackets: JSONB [{min, max, rate, base_tax}]

Deduction
  id, tenant_id, name, type: fixed | percentage | formula
  pre_tax: boolean, applies_to (all | employee_group)
```

#### Features

- Gross-to-net engine — earnings, statutory deductions (tax, pension, UIF/NI), voluntary deductions, net pay
- Tax table management — annual updates by country; South Africa (SARS PAYE), UK (HMRC PAYE), US (Federal + State) supported in v1
- Payslip PDF generation and email distribution; employee can view in self-service portal
- Payroll run history and full audit trail — who approved, what changed
- Multi-currency — exchange rate applied per pay run
- Bank file export — NACHA (US), BACS (UK), EFT (SA) standard formats
- Statutory reporting — IRP5/IT3a (SA), P60 (UK), W-2 (US)
- Bonus & incentive processing — ad-hoc payment linked to a pay run
- Accounting sync — export journal entries to Xero, QuickBooks, Sage

---

### Module 5 — Recruitment / ATS

#### Data Model

```
JobPosting
  id, tenant_id, title, department_id, location
  description_html, requirements_html
  type: full_time | part_time | contract | internship
  status: draft | open | closed | on_hold
  published_at, closes_at
  channels: JSONB (LinkedIn, Indeed, internal, etc.)

Candidate
  id, first_name, last_name, email, phone
  cv_url, linkedin_url
  source: channel name
  ai_screening_score, ai_screening_summary

Application
  id, job_posting_id, candidate_id
  stage: applied | screened | phone_screen | interview_1 | interview_2 |
         assessment | offer | hired | rejected | withdrawn
  notes, rejection_reason, referral_employee_id

Interview
  id, application_id, scheduled_at, duration_minutes
  interviewer_ids: int[]
  format: video | in_person | phone
  feedback_submitted_at, rating, notes

Offer
  id, application_id, salary, start_date, expiry_date
  status: draft | sent | accepted | rejected | expired
  letter_url
```

#### Features

- Job posting creation with rich text editor
- Multi-channel publish — LinkedIn, Indeed, company careers page (embeddable widget)
- CV upload (PDF/DOCX) + AI parsing into structured fields
- AI screening — Claude scores CV against job requirements (0–100), summarises fit; HR can set auto-reject threshold
- Kanban pipeline board — drag cards between stages
- Interview scheduling — calendar integration (Google Calendar, Outlook); candidate self-scheduling link
- Hiring manager collaboration — scorecard comments, @mentions
- Offer letter generation from template; e-signature via DocuSign
- Candidate comms — email + SMS templates, bulk send, open-rate tracking
- Analytics — time-to-hire, time-per-stage, source breakdown, offer acceptance rate

---

### Module 6 — Onboarding

#### Features

- Checklist templates — global or role/department-specific; items can be assigned to HR, IT, Manager or new hire
- Welcome email automation — triggered on `Employment.start_date - N days`; configurable via workflow builder
- Document collection — new hire receives task list to upload ID, bank details, signed contract; e-signature supported
- Equipment & IT access requests — tasks auto-created for IT team; tracks fulfilment
- Buddy assignment — HR matches buddy from same department; buddy receives orientation checklist
- Onboarding progress tracker — HR dashboard shows % complete per new hire, overdue items flagged
- New hire self-service portal — restricted access during pre-boarding, expanded on day one
- Probation tracking — countdown badge on employee profile; reminder at 30/14/7 days before end date

---

### Module 7 — Performance Management

#### Data Model

```
ReviewCycle
  id, tenant_id, name, type: annual | biannual | quarterly | probation
  period_start, period_end, status: setup | active | closed

ReviewForm
  id, review_cycle_id, template_id
  employee_id, reviewer_id, type: self | manager | peer | upward
  status: pending | in_progress | submitted | acknowledged
  sections: JSONB (questions + responses + ratings)
  overall_rating, comments

Goal
  id, employee_id, review_cycle_id (nullable for ongoing goals)
  title, description, type: individual | team | company
  metric_type: percentage | number | boolean
  target_value, current_value
  due_date, status: not_started | in_progress | at_risk | achieved | missed

OneOnOne
  id, manager_id, employee_id, scheduled_at
  agenda_items: JSONB, notes, action_items: JSONB

PIP
  id, employee_id, start_date, end_date, status
  objectives: JSONB, check_in_dates: date[], outcome
```

#### Features

- OKR framework — company → team → individual goal cascading
- Configurable review templates — rating scales (1–5, 1–10, custom), free-text, competency selection
- 360 feedback — peer nomination; anonymisation option
- Review cycle automation — launch, nudge reminders, close cycle on deadline
- 1-on-1 meeting tool — shared agenda, action item tracker, meeting history
- PIPs — structured plan with check-in schedule; legal safeguard mode hides from employee until manager publishes
- Skill gap analysis — compare employee competency ratings against role benchmark
- Performance dashboard — distribution curves, high/low performer identification

---

### Module 8 — Learning & Development (LMS)

#### Features

- Course builder — sections, lessons (video/PDF/SCORM/article), drag-and-drop ordering
- Self-paced and instructor-led modes
- Quizzes with pass threshold; auto-retry logic
- Certification tracking — expiry date alerts; certificate PDF on completion
- Learning paths — ordered sequence of courses; auto-enrol by role/department
- Compliance training — mandatory courses flagged; HR dashboard shows overdue employees
- External content — SCORM 1.2/2004 import; LTI 1.3 for platforms like Coursera/LinkedIn Learning
- Training completion reports with time spent, scores, pass rates

---

### Module 9 — Benefits Administration

#### Features

- Benefits plan setup — medical aid, group life, disability, provident/pension, flexible spend
- Tiered plans — e.g. Basic / Standard / Premium with cost tables
- Self-enrolment portal — employee selects plan during onboarding or open enrolment window
- Open enrolment workflow — HR sets window dates; employees receive reminder; auto-close and lock after deadline
- Life events — employee can trigger re-enrolment on marriage, new child, divorce
- Cost reporting — employer vs employee contributions; monthly and annual views
- Benefits statements — personalised PDF showing total compensation including benefits value

---

### Module 10 — Shift Scheduling / Workforce Planning

#### Features

- Visual drag-and-drop shift builder — week and month views
- Shift templates — save and reapply by role or department
- Shift swap — employee requests swap; notifies target; manager approves
- Availability management — employees set recurring or one-off unavailability
- Overtime and coverage gap alerts — flags understaffed shifts and employees approaching overtime limits
- Publish & notify — publish schedule sends push notification to affected employees
- Roster export — PDF/CSV

---

### Module 11 — Expense Management

#### Features

- Mobile receipt capture — photo upload; OCR extracts amount, date, vendor
- Expense categories and per diem policies — daily limits by country/role
- Multi-level approval workflows (shares workflow engine with Leave)
- Payroll-linked reimbursement — approved expenses exported to next payroll run
- Policy enforcement — system flags spend over policy limit before submission
- Reports — spend by category, employee, department, project code

---

### Module 12 — HR Analytics & Reporting

#### Features

- Pre-built report library — headcount, turnover, leave utilisation, payroll cost, time-to-hire, absenteeism
- Custom report builder — drag-and-drop columns from any module; filters; grouping; visualisations
- Diversity & inclusion dashboard — gender, age, ethnicity breakdowns; EEA compliance view
- Workforce demand forecasting — ML model projects headcount needs 3/6/12 months out
- Scheduled delivery — reports emailed on a cron schedule to named recipients
- Export — CSV, Excel, PDF

---

### Module 13 — Employee Engagement & Wellness

#### Features

- Survey builder — custom questions; rating/NPS/open text types
- Pulse surveys — short recurring surveys (weekly/monthly); trend charts
- eNPS — standard employer NPS question; benchmark scoring
- Anonymous feedback — submissions stripped of identifiers before HR can view
- Peer recognition — employees nominate peers with a message; visible on company newsfeed
- Milestone celebrations — automated birthday and work anniversary notifications to team
- Wellness programs — link to external programs; track participation
- Burnout alerts — AI flags employees who have taken zero leave in 90 days or have consistently high overtime

---

### Module 14 — Employee Self-Service Portal

Thin UI layer over existing modules exposing employee-appropriate views:

- Dashboard — upcoming leave, payslips, tasks, announcements
- Profile editor — personal info, emergency contacts, banking details (with approval workflow for banking changes)
- Leave request & balance view
- Payslip history & tax certificate download
- Clock in/out widget
- My documents — download contracts, policies
- Expense claim submission
- Team calendar view
- Learning — enrolled courses

---

### Module 15 — Offboarding

#### Features

- Resignation/termination workflow — initiated by employee (resignation) or HR (termination/redundancy)
- Exit interview — scheduled automatically; digital form + optional video interview link
- Asset return checklist — laptop, access card, uniform; item-by-item sign-off
- IT access revocation tasks — auto-created for IT team on termination initiation; escalation if incomplete by exit date
- Final payroll trigger — calculates outstanding leave payout, pro-rated salary, deductions
- Knowledge transfer — assign documentation tasks to departing employee and their successor
- Rehire eligibility flag — HR sets eligible/ineligible with notes; surfaced in ATS if same person applies
- Alumni records — read-only archived profile retained per data policy

---

### Module 16 — Succession Planning & Talent Management

#### Features

- Talent pool — HR tags employees as high-potential; segmented pools by level/function
- Career path mapping — define progression paths between roles; employee self-nominates interest
- Succession readiness scoring — 1–3 scale (ready now / 1–2 years / 2+ years) set by HR/manager
- 9-box grid — plots performance vs potential; visual tool updated each review cycle
- Leadership pipeline dashboard — shows depth of bench at each leadership level
- Skills & competency matrix — per-role benchmarks vs employee actuals; gap heatmap
- Internal job board — open roles posted internally before external; application tracked in ATS with internal-hire flag

---

### Module 17 — Compensation Management

#### Features

- Salary band management — grade/band framework; min/mid/max ranges; linked to job levels
- Pay equity analysis — compare pay within same grade by gender/ethnicity; flags statistical outliers
- Merit increase workflow — HR uploads merit budget; managers propose increases within budget; HR approves
- Bonus & incentive planning — target bonus percentages by grade; actual payout calculated from performance rating
- Industry benchmarking — upload market data or integrate with benchmark provider (e.g. PayScale, Mercer feed)
- Compensation approval chain — manager → HR → CFO for increases above threshold
- Total compensation statement — personalised PDF: base + benefits + bonus + equity

---

### Module 18 — Compliance & Legal

#### Features

- Labour law tracker — checklist of obligations by country; HR marks compliance status
- Statutory reporting — UIF/SDL/COIDA (SA), RTI (UK), EEO-1 (US) generation
- Employment Equity reporting — SA EEA2/EEA4 auto-generated from workforce data
- POPIA/GDPR controls — data subject request portal; data retention automation; processing register
- Contract expiry alerts — 30/14/7-day warnings for fixed-term contracts
- Disciplinary case management — incident logging, hearing scheduling, outcome recording; full case file
- Grievance tracking — submission, investigation assignment, outcome, appeal
- Audit log — every create/update/delete action logged with user, timestamp, before/after values; tamper-evident; 7-year retention

---

### Module 19 — Notifications & Workflow Automation

#### Workflow Engine

A rule-based workflow engine where each rule has:
- **Trigger** — HR event (e.g. `leave.requested`, `employee.probation_end_approaching`)
- **Conditions** — optional filters (e.g. `department = Engineering`)
- **Actions** — send email, send SMS, send in-app, create task, update field, call webhook

#### Features

- Visual workflow builder — drag-and-drop trigger/condition/action canvas
- Approval routing — multi-level with configurable delegation rules
- Escalation — stalled approval auto-escalates after N hours
- Reminders — cron-based; contract expiry, probation end, certification expiry, review deadlines
- In-app notification centre — bell icon with unread count, grouped by type
- Email & SMS delivery with open/click tracking
- Webhook outbound — fire JSON payload to external URL on any trigger

---

### Module 20 — AI & Smart Features

All AI features use the Anthropic Claude API.

| Feature | Model | Description |
|---|---|---|
| HR Chatbot | claude-fable-5 | Conversational assistant answers policy questions, helps employees with self-service tasks, explains pay components. RAG over company documents. |
| Predictive attrition | claude-haiku-4-5 | Monthly scoring of flight-risk probability based on engagement survey trends, leave patterns, performance data, tenure. |
| AI resume screening | claude-haiku-4-5 | Scores and summarises CVs against JD; configurable prompt per job; threshold-based auto-shortlist/reject. |
| Anomaly detection | claude-haiku-4-5 | Flags unusual attendance (chronic tardiness pattern), leave (sudden spike), or expense (outlier amounts) for HR review. |
| Smart report generation | claude-fable-5 | Natural language query ("show me turnover by department last quarter") generates and executes report. |
| Performance insights | claude-fable-5 | Analyses review data to surface coaching suggestions for managers; identifies team-level skill gaps. |

All AI calls are logged with input/output for audit; employees are notified when AI-assisted decisions affect them; HR can override all AI scores.

---

### Module 21 — Mobile App

**Platform:** React Native (Expo), targeting iOS 16+ and Android 13+

| Feature | Notes |
|---|---|
| Leave request & approval | Full workflow parity with web |
| Clock in/out | GPS capture, geofence enforcement |
| Payslip viewer | PDF download |
| Push notifications | FCM (Android) + APNs (iOS) |
| Offline mode | Last 7 days of timesheet cached locally; syncs on reconnect |
| Biometric unlock | Face ID / fingerprint for app login |
| Team calendar | Read-only |
| Expense claim | Camera receipt capture |

---

### Module 22 — Integrations & API

#### Public REST API

- OpenAPI 3.1 specification published at `/api/docs`
- OAuth 2.0 (client credentials + authorization code flows)
- Rate limiting: 1,000 req/min per tenant
- Webhook subscriptions — HR Admin registers URL + event types; HMAC-signed payloads

#### Native Integrations (v1)

| System | Integration Type |
|---|---|
| Slack | Bot: leave approvals, HR chatbot, announcements |
| Microsoft Teams | Bot + Adaptive Cards for approvals |
| Google Workspace | SSO, Calendar sync, Directory sync |
| Xero | Payroll journal export |
| QuickBooks | Payroll journal export |
| Sage | Payroll journal export |
| LinkedIn | Job posting publish |
| Indeed | Job posting publish |
| DocuSign | E-signature |
| Zapier | Webhook trigger/action connector |

#### SSO

SAML 2.0 and OIDC supported. Tested with Okta, Azure AD, Google, Ping Identity.

---

## 5. Non-Functional Requirements

### 5.1 Performance

| Metric | Target |
|---|---|
| API p95 response time | < 200ms (reads), < 500ms (writes) |
| Page load (web, LCP) | < 2.5s on 4G |
| Payroll run (1,000 employees) | < 60 seconds |
| Report generation | < 10s for up to 50,000 rows |

### 5.2 Scalability

- Horizontal scaling of API tier via Kubernetes HPA
- Database read replicas for report queries
- BullMQ for async jobs; concurrency tuned per queue

### 5.3 Security

- TLS 1.3 everywhere
- Encryption at rest (AES-256) for database and S3
- Field-level encryption for ID numbers, banking details
- OWASP Top 10 mitigations enforced; annual pen test
- POPIA / GDPR compliant data handling
- SOC 2 Type II target within 18 months of launch

### 5.4 Availability

- 99.9% monthly uptime SLA (< 8.7h downtime/year)
- Automated backups every 6 hours; PITR 30 days
- Disaster recovery RTO < 4h, RPO < 1h

### 5.5 Internationalisation

- i18n from day one (react-i18next / i18next on server)
- Date/time/number formatting per locale
- Multi-currency, multi-timezone
- Initial languages: English (ZA, UK, US), Afrikaans

---

## 6. Data Privacy

- Data residency — tenants choose AWS region at sign-up; data does not leave that region
- Right to access / erasure — built-in DSAR workflow in Compliance module
- Data retention policies — configurable per document type; automated deletion job
- Consent tracking — employee accepts terms + privacy policy on first login; logged with timestamp

---

## 7. Accessibility

- WCAG 2.1 AA compliance
- Keyboard navigation throughout
- Screen reader tested (NVDA/JAWS/VoiceOver)

---

## 8. Key Integrations Diagram

```
HRCore
  ├── Auth providers  →  Okta, Azure AD, Google
  ├── Communication   →  Slack, MS Teams
  ├── Calendar        →  Google Calendar, Outlook
  ├── E-signature     →  DocuSign
  ├── Accounting      →  Xero, QuickBooks, Sage
  ├── Job boards      →  LinkedIn, Indeed
  ├── AI              →  Anthropic Claude API
  ├── SMS             →  Twilio
  ├── Email           →  Resend
  └── Automation      →  Zapier (webhooks)
```

---

## 9. Open Questions / Decisions Pending

| # | Question | Owner | Due |
|---|---|---|---|
| 1 | Biometric / facial recognition — in-house or vendor (e.g. AWS Rekognition)? | Engineering | Sprint 3 |
| 2 | Payroll tax engine — build vs license (e.g. Symmetry, Avalara)? | Product | Sprint 5 |
| 3 | Mobile — Expo managed vs bare workflow? | Mobile lead | Sprint 1 |
| 4 | E-signature — DocuSign vs Dropbox Sign pricing? | Product | Sprint 4 |
| 5 | Benchmark data provider for compensation module? | Product | Sprint 15 |
