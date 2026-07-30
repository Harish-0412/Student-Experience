# AstraPath
## Complete Frontend Product, Page, Component, and Implementation Blueprint

**Document version:** 2.0  
**Application roles:** **Student** and **Admin only**  
**Frontend type:** Responsive web application with progressive mobile support  
**Recommended framework:** Next.js App Router with TypeScript  
**Backend integration:** REST/OpenAPI, SSE, and WebSocket streaming

---

# 1. Purpose

This document defines the complete frontend implementation of AstraPath.

It specifies:

- Student and Admin experiences
- Application routes
- Every required page
- Page sections, widgets, actions, states, and API dependencies
- Navigation
- Design system
- Component architecture
- State management
- Real-time agent progress
- Forms and validation
- Accessibility
- Security
- Testing
- Folder structure
- Frontend implementation phases

No teacher, parent, mentor, coordinator, or other application role is included.

---

# 2. Frontend Technology Stack

| Concern | Selected Technology |
|---|---|
| Framework | Next.js App Router |
| Language | TypeScript |
| UI | React |
| Styling | Tailwind CSS |
| Component primitives | Radix UI or shadcn/ui |
| Server-state management | TanStack Query |
| Local interaction state | Zustand |
| Forms | React Hook Form |
| Validation | Zod |
| API client | OpenAPI-generated typed client |
| Streaming | Native EventSource for SSE; WebSocket for tutor/focus when needed |
| Charts | Recharts |
| Goal and competency graph | Cytoscape.js or React Flow |
| Calendar | FullCalendar |
| Rich text | TipTap |
| File uploads | Uppy or controlled native upload components |
| Tables | TanStack Table |
| Dates | date-fns |
| Testing | Vitest, React Testing Library, Playwright |
| Error reporting | Sentry-compatible frontend SDK |
| Analytics | Privacy-preserving product analytics |
| Package management | pnpm |
| Formatting and linting | ESLint, Prettier |
| Component documentation | Storybook |

## 2.1 Frontend Architecture Rule

Use:

- Server Components for initial read-heavy page shells
- Client Components for interactive dashboards, forms, timers, charts, and streaming
- TanStack Query for API server state
- Zustand only for temporary UI state
- URL search parameters for filters that should be shareable
- Local storage only for non-sensitive preferences
- Secure HTTP-only cookies for sessions

Do not place access tokens in browser local storage.

---

# 3. Role-Based Route Groups

```text
app/
├── (public)/
├── (auth)/
├── student/
└── admin/
```

## 3.1 Student Route Protection

Only authenticated users with role `student` can access `/student/**`.

## 3.2 Admin Route Protection

Only authenticated users with role `admin` and required scope can access `/admin/**`.

## 3.3 Unauthorized Behavior

- Not signed in → redirect to sign in
- Signed in with wrong role → show 403 page
- Expired session → preserve safe return URL and request sign in
- Missing resource ownership → show 404, not another student’s existence
- Insufficient Admin scope → show restricted-access page and audit the attempt

---

# 4. Information Architecture

## 4.1 Student Navigation

Primary sidebar:

1. Home
2. Goals
3. Today
4. Focus
5. Tutor
6. Assessments
7. Progress
8. Portfolio
9. Resources
10. Notifications

Secondary:

- Profile and Preferences
- Help and Feedback
- Sign out

## 4.2 Admin Navigation

Primary sidebar:

1. Dashboard
2. Students
3. Review Queue
4. Risks
5. Agents
6. Workflows
7. Knowledge
8. Resources
9. Assessments
10. Models and Prompts
11. Analytics
12. Audit Logs
13. System Health
14. Policies
15. Settings

## 4.3 Responsive Navigation

- Desktop: persistent sidebar
- Tablet: collapsible sidebar
- Mobile: bottom navigation for five primary Student pages and drawer for remaining pages
- Admin mobile: view-only emergency dashboard; complex editing optimized for desktop

---

# 5. Design System

## 5.1 Visual Principles

- Calm, focused, and supportive
- Clear hierarchy
- Minimal visual noise
- Progress without pressure
- Accessible contrast
- Explainability visible near recommendations
- Status expressed through icon, label, and text, not color alone

## 5.2 Design Tokens

Define:

- Color primitives
- Semantic status tokens
- Typography scale
- Spacing scale
- Radius
- Shadows
- Motion durations
- Breakpoints
- Z-index layers

Semantic statuses:

```text
neutral
information
success
warning
danger
blocked
pending
in_review
agent_running
input_required
```

## 5.3 Core Components

- `AppShell`
- `Sidebar`
- `TopBar`
- `MobileNavigation`
- `PageHeader`
- `Breadcrumbs`
- `Card`
- `StatCard`
- `Metric`
- `StatusBadge`
- `ProgressBar`
- `CircularProgress`
- `Timeline`
- `StepIndicator`
- `DataTable`
- `FilterBar`
- `EmptyState`
- `ErrorState`
- `Skeleton`
- `Toast`
- `Dialog`
- `Drawer`
- `CommandPalette`
- `ApprovalCard`
- `ExplainabilityCard`
- `AgentActivityPanel`
- `RiskCard`
- `EvidenceCard`
- `MasteryBadge`
- `CompetencyGraph`
- `MilestoneTimeline`
- `FocusTimer`
- `TutorMessage`
- `CitationList`
- `FileUploader`
- `AuditDiffViewer`

## 5.4 Motion

Motion must:

- Be subtle
- Respect reduced-motion preference
- Never block input
- Avoid celebratory animation when the student has opted out
- Use progress animation only when status is known
- Avoid fake indeterminate progress for completed operations

---

# 6. Global Application Shell

## 6.1 Top Bar

Student:

- Current page title
- Goal switcher
- Global search
- Agent status indicator
- Notifications
- Profile menu

Admin:

- Environment badge
- Global student/workflow search
- Incident indicator
- Review queue count
- Notifications
- Admin menu

## 6.2 Agent Status Indicator

States:

- Idle
- Working
- Waiting for Student
- Waiting for Admin
- Completed
- Failed

Clicking opens `AgentActivityPanel` showing:

- Workflow name
- Active agent
- Completed steps
- Current status
- Explainable summary
- Cancel action where safe
- Retry action when permitted

Never reveal private chain-of-thought. Show only safe execution summaries and evidence references.

## 6.3 Global Command Palette

Student actions:

- Create goal
- Open today’s plan
- Start focus session
- Ask Tutor
- Upload evidence
- Request replan

Admin actions:

- Search student
- Open review queue
- Find workflow
- Find agent
- Create resource
- Create assessment template
- Open incident dashboard

---

# 7. Public and Authentication Pages

## 7.1 Landing Page — `/`

### Sections

- Hero statement
- Product explanation
- Goal-to-achievement workflow
- Feature cards
- Student journey example
- Privacy and student-control statement
- Sign-in and create-account actions
- Footer

### Actions

- Create Student account
- Sign in
- Learn how planning works

## 7.2 Student Registration — `/register`

### Fields

- Name
- Email
- Password or identity-provider flow
- Timezone
- Terms acceptance
- Privacy notice acceptance

### States

- Email already exists
- Weak password
- Verification required
- Registration success

Admin accounts are not self-created publicly.

## 7.3 Sign In — `/login`

### Components

- Email and password or SSO
- Remember this device
- Forgot password
- Role-aware redirect
- Security message

## 7.4 Forgot and Reset Password

Routes:

```text
/forgot-password
/reset-password
/verify-email
```

## 7.5 Access Error Pages

```text
/403
/404
/500
/maintenance
/session-expired
```

---

# 8. Student Onboarding

Route: `/student/onboarding`

Use a resumable multi-step wizard.

## Step 1 — Welcome

- Explain what AstraPath will do
- Explain Student control
- Show expected completion time
- Continue or skip optional setup

## Step 2 — Education Context

- Education level
- Current area of study
- Optional institution name
- Current semester or stage
- Relevant prior courses

## Step 3 — Existing Skills

- Searchable competency selector
- Self-reported level
- Optional supporting evidence
- “Not sure” option

## Step 4 — Availability

- Weekly calendar
- Fixed classes or work
- Preferred study windows
- Maximum daily study time
- Break preference
- Exam or busy periods

## Step 5 — Learning Preferences

- Preferred content formats
- Preferred explanation depth
- Project versus theory balance
- Session-length preference
- Notification preference
- Language preference

Do not present learning-style categories as fixed scientific identities.

## Step 6 — Access and Constraints

- Device availability
- Internet constraints
- Budget preference
- Accessibility settings
- Other constraints

## Step 7 — Privacy and Consent

- Calendar read permission
- Uploaded-document processing
- Notification permission
- Data retention choices
- AI assistance explanation

## Step 8 — Review

- Profile summary
- Edit links
- Save and continue
- Profile completeness indicator

### API

```text
GET   /v1/student/profile
PATCH /v1/student/profile
POST  /v1/student/onboarding/complete
```

### Error Recovery

- Autosave each completed step
- Resume after refresh
- Offline draft for non-sensitive form values
- Never lose uploaded file state silently

---

# 9. Student Home Dashboard

Route: `/student`

## Primary Purpose

Tell the Student what matters now without overwhelming them.

## Layout

### Section A — Greeting and Goal Health

- Greeting
- Active goal switcher
- Goal health status
- Target date
- Next milestone
- “Why this status?” action

### Section B — Today’s Top Actions

Display no more than three primary tasks.

Each task card contains:

- Title
- Goal and milestone
- Estimated time
- Priority
- Completion evidence
- Start action
- Reschedule action
- “Why this task?” explanation

### Section C — Focus Launch

- Selected recommended task
- Focus mode selector
- Duration
- Start button
- Last session summary

### Section D — Progress Snapshot

- Activity progress
- Mastery progress
- Milestone progress
- Weekly consistency
- Planned versus actual time

### Section E — Agent Recommendation

- Recommendation
- Evidence used
- Expected impact
- Accept, dismiss, or explain
- Report incorrect recommendation

### Section F — Open Risk or Blocker

Only show actionable risks.

- Risk type
- Severity
- Evidence summary
- Suggested action
- Request replan
- Mark resolved

### Section G — Upcoming

- Assessments
- Milestones
- Reviews
- Busy periods

### Empty State

When no goal exists:

- Explain value
- Create first goal button
- Show sample goals

### APIs

```text
GET /v1/student/dashboard
GET /v1/student/daily-plan
GET /v1/student/progress
GET /v1/student/risks
GET /v1/student/notifications
```

---

# 10. Goals List

Route: `/student/goals`

## Components

- Page header
- Create Goal button
- Filter: active, paused, completed, archived
- Sort: priority, target date, recently updated
- Goal cards or table
- Goal template suggestions

## Goal Card

- Title
- Goal category
- Status
- Target date
- Goal-health badge
- Activity and mastery mini-progress
- Next milestone
- Open risk count
- Continue action
- More menu

## Actions

- Open
- Pause
- Resume
- Duplicate as new goal
- Archive
- Export summary

Deleting a goal should use soft deletion and clear consequences.

---

# 11. Create Goal Wizard

Route: `/student/goals/new`

## Step 1 — Goal Statement

- Large text input
- Example prompts
- Optional goal-template selection
- Voice input where supported

## Step 2 — Target and Motivation

- Target date
- Priority
- Why this matters
- Mandatory outcome
- Optional outcome

## Step 3 — Constraints

- Weekly time budget
- Known busy periods
- Budget
- Device restrictions
- Existing commitments

## Step 4 — Agent Clarification

Live agent workflow:

- Show safe activity timeline
- Present one clarification at a time
- Allow Student to edit inferred information
- Show assumptions

## Step 5 — Feasibility Scenarios

Cards:

- Recommended scenario
- Keep scope and increase effort
- Keep effort and extend date
- Reduce optional scope

Each card shows:

- Expected effort range
- Weekly workload
- Main risks
- Trade-offs

## Step 6 — Diagnostic

- Explain purpose
- Start diagnostic
- Skip with reduced confidence
- Estimated duration
- Autosave attempt

## Step 7 — Generated Plan Review

- Goal statement
- Competency map
- Milestones
- Weekly load
- Resource examples
- Risks and assumptions
- Plan alternatives
- Approve
- Request changes
- Save draft

### Workflow Status UI

```text
Profile checked
Goal clarified
Feasibility analyzed
Diagnostic prepared
Skill gaps analyzed
Path generated
Milestones created
Schedule generated
Waiting for approval
```

### API

```text
POST /v1/student/goals
GET  /v1/workflows/{workflow_id}
GET  /v1/workflows/{workflow_id}/events
POST /v1/student/goals/{goal_id}/approvals/{approval_id}
```

---

# 12. Goal Detail

Route: `/student/goals/[goalId]`

Use tabs.

## Tab 1 — Overview

- Goal statement
- Success criteria
- Status
- Target date
- Goal health
- Feasibility summary
- Current milestone
- Top next actions
- Open risks
- Latest plan change
- Pause or request replan

## Tab 2 — Roadmap

- Interactive competency graph
- Core path
- Optional branches
- Locked and unlocked nodes
- Mastery level per node
- Prerequisite explanation
- Resource and assessment links

Graph interactions:

- Zoom
- Fit
- Search node
- Filter core/optional
- Open detail drawer
- Keyboard navigation
- Accessible list fallback

## Tab 3 — Milestones

- Vertical or horizontal timeline
- Status
- Target dates
- Acceptance criteria
- Evidence
- Dependencies
- Assessments
- Replan history

## Tab 4 — Schedule

- Weekly calendar
- Study blocks
- Buffers
- Conflicts
- Drag to propose reschedule
- Confirm schedule change
- Availability editor

## Tab 5 — Evidence

- Evidence gallery
- Verification status
- Criteria matched
- Feedback
- Upload action
- Resubmit action

## Tab 6 — Progress

- Activity
- Milestone completion
- Mastery
- Time trend
- Forecast
- Risk history

## Tab 7 — Plan History

- Version list
- Change reason
- Side-by-side diff
- Student approval
- Admin review where present
- Restore as new proposal, not destructive rollback

## Tab 8 — Settings

- Goal priority
- Target date request
- Notification settings
- Visibility and export
- Pause
- Archive

---

# 13. Today / Daily Planner

Route: `/student/today`

## Header

- Date
- Active goal filter
- Daily capacity
- Planned load
- Energy check-in

## Plan Sections

### Essential

Maximum three tasks by default.

### Recommended

Secondary tasks.

### Minimum Viable Day

A reduced plan for constrained days.

### Stretch

Optional task shown only when core work is done.

## Task Card

- Checkbox or status control
- Title
- Competency
- Milestone
- Priority
- Estimated time
- Scheduled time
- Evidence requirement
- Start Focus
- Ask Tutor
- Reschedule
- Mark blocked
- Complete

## Rescheduling

When dragging a task:

- Show conflicts
- Show deadline impact
- Do not write until confirmed
- Send change request to Schedule Agent

## Daily Reflection

- What was completed?
- What was difficult?
- How accurate were estimates?
- What should change tomorrow?

---

# 14. Calendar

Route: `/student/calendar`

## Views

- Day
- Week
- Month
- Agenda

## Items

- Study blocks
- Milestones
- Assessments
- Busy periods
- Revision
- Buffer
- External calendar items when authorized

## Actions

- Add availability
- Add busy period
- Propose task move
- Regenerate week
- Connect or disconnect calendar
- Resolve conflict

## Rules

- External calendar writes require explicit confirmation.
- Show AstraPath items distinctly.
- Provide keyboard-operable scheduling.
- Provide list fallback on small screens.

---

# 15. Focus Page

Route: `/student/focus`

## Pre-Session Setup

- Select task
- Define intended outcome
- Choose mode:
  - Quick Start
  - Pomodoro
  - Deep Work
  - Guided Study
  - Practice Test
  - Project Sprint
  - Revision
  - Low-Energy
- Select duration
- Optional distraction blocker guidance
- Start

## Active Session

- Large timer
- Intended outcome
- Current task steps
- Pause
- Stop
- Mark step complete
- Capture distraction
- Ask Tutor
- Request hint
- Mark blocked
- Session-status indicator

## Agent Check-ins

- Non-intrusive
- User-configurable
- Never use guilt
- Can be muted

## Completion

- Outcome achieved?
- Actual work completed
- Difficulty
- Reflection
- Evidence upload
- Suggested next step
- Save session

## Recovery

- Browser refresh restores active session
- Server remains source of truth
- Timer uses timestamps, not only client intervals

---

# 16. Tutor

Route: `/student/tutor`

## Layout

- Conversation list
- Active conversation
- Context side panel
- Tutor mode selector
- Input composer
- Source panel

## Tutor Modes

- Explain
- Socratic
- Hint only
- Worked example
- Debug with me
- Revision
- Interview practice
- Teach-back

## Message Features

- Markdown
- Code blocks
- Equations
- Tables
- Citations
- Copy
- Rate response
- Report issue
- Convert explanation into note
- Create practice task

## Context Panel

- Current goal
- Current competency
- Student-selected files
- Allowed resources
- Privacy indicator

The Student controls which files enter a conversation.

## Integrity UI

For prohibited graded work:

- Explain limitation
- Offer guidance, outline, hints, or practice
- Avoid accusatory language

## Streaming

- Token stream
- Tool status
- Citation retrieval status
- Cancel generation
- Retry
- Continue

---

# 17. Assessments Center

Route: `/student/assessments`

## Sections

- Due
- Recommended practice
- Completed
- Diagnostic
- Mock interviews
- Project reviews

## Assessment Card

- Title
- Competency
- Type
- Duration
- Attempts
- Due date
- Pass threshold
- Start or review

## Filters

- Goal
- Competency
- Type
- Status
- Date

---

# 18. Assessment Player

Route: `/student/assessments/[assessmentId]`

## Header

- Assessment title
- Timer if applicable
- Progress
- Save state
- Exit policy

## Question Types

- Multiple choice
- Short answer
- Numerical
- Code
- Debugging
- Essay plan
- Oral recording
- File upload
- Case study

## Requirements

- Autosave
- Keyboard navigation
- Screen-reader labels
- Connection-loss indicator
- Confirmation before final submit
- Honor time policy
- Do not expose answer key

## Submission State

- Uploading
- Submitted
- Scoring
- Evidence review
- Admin review
- Completed

---

# 19. Assessment Result

Route: `/student/assessments/[assessmentId]/result`

## Components

- Score where applicable
- Competency impact
- Correct and incorrect areas
- Rubric feedback
- Misconceptions
- Recommended review
- Retake eligibility
- Mastery change
- Ask Tutor about a question
- Add review tasks to plan

Do not make mastery changes appear as permanent labels.

---

# 20. Evidence Center

Route: `/student/evidence`

## Views

- All evidence
- Needs action
- Verified
- In review
- Resubmission required

## Upload Flow

1. Select goal, milestone, or task.
2. Select evidence type.
3. Upload file or permitted link.
4. Preview.
5. Confirm processing consent.
6. Submit.
7. Show verification status.

## Evidence Detail Drawer

- File preview
- Checksum
- Submission time
- Acceptance criteria
- Verification result
- Quality notes
- Feedback
- Resubmit
- Appeal or report incorrect result

## Supported Types

- Document
- Image
- Notebook
- Source archive
- Repository link
- Certificate
- Presentation
- Audio or video explanation
- Reflection
- Assessment artifact

---

# 21. Progress Page

Route: `/student/progress`

## Summary

- Goal health
- Activity progress
- Milestone progress
- Mastery progress
- Time remaining
- Forecast range

## Charts

- Planned versus actual time
- Weekly task completion
- Mastery by competency
- Assessment trend
- Focus time
- Risk and recovery timeline

## Rules

- Use clear labels
- Explain calculation
- Provide table alternative
- Do not compare Students publicly
- Avoid a single gamified score

## Filters

- Goal
- Date range
- Competency
- Milestone
- Activity type

---

# 22. Mastery Page

Route: `/student/mastery`

## Competency Matrix

Columns:

- Competency
- Required level
- Estimated level
- Confidence range
- Evidence strength
- Last assessed
- Next recommended action

## Competency Detail

- Description
- Prerequisites
- Evidence
- Assessment history
- Common errors
- Mastery explanation
- Reassessment date
- Resources
- Tutor action

---

# 23. Portfolio

Route: `/student/portfolio`

## Purpose

Turn verified work into a student-controlled achievement portfolio.

## Sections

- Featured projects
- Verified competencies
- Certificates
- Assessment achievements
- Learning journey
- Reflection
- Export history

## Actions

- Choose featured evidence
- Edit public description
- Hide private evidence
- Generate PDF or shareable export
- Revoke shared link
- Preview as viewer

No portfolio item becomes public by default.

---

# 24. Resources

Route: `/student/resources`

## Sections

- Recommended for current task
- Saved
- Recently used
- Resource bundles
- Offline-friendly
- Free resources

## Resource Card

- Title
- Provider
- Format
- Difficulty
- Estimated time
- Cost type
- Accessibility information
- Why recommended
- Open
- Save
- Not useful
- Request alternative

---

# 25. Notifications

Route: `/student/notifications`

## Types

- Daily-plan ready
- Assessment due
- Milestone approaching
- Evidence result
- Replan proposal
- Risk action
- Agent needs input
- System message

## Controls

- Mark read
- Filter
- Open related item
- Mute category
- Notification settings

Notifications must be actionable and rate-limited.

---

# 26. Student Settings

Route: `/student/settings`

Tabs:

## Profile

- Name
- Education details
- Timezone
- Language

## Learning Preferences

- Formats
- Tutor depth
- Session mode
- Challenge level

## Availability

- Weekly time
- Busy periods
- Focus windows

## Notifications

- Categories
- Channels
- Quiet hours
- Frequency

## Privacy and Data

- Calendar permission
- File-processing consent
- Conversation retention
- Export data
- Delete account request
- Connected services

## Accessibility

- Font scale
- Contrast
- Reduced motion
- Captions
- Keyboard hints
- Timer announcements

## Security

- Password
- Sessions
- Two-factor authentication
- Sign out all devices

---

# 27. Student Help and Feedback

Route: `/student/help`

- Search help
- Product guides
- Agent explanation
- Report incorrect answer
- Report resource
- Report technical issue
- Contact support
- View submitted reports

---

# 28. Admin Dashboard

Route: `/admin`

## Header Metrics

- Active Students
- Active Goals
- Workflows running
- Review items
- High-severity risks
- Agent failures
- MCP/A2A endpoint health

## Sections

### Review Queue Summary

- Evidence
- Assessment
- Risk
- Goal policy
- Replan
- Resource

### Agent Health

- Success rate
- Latency
- Low-confidence rate
- Tool failure rate
- Cost
- Drift alerts

### Workflow Health

- Running
- Waiting for Student
- Waiting for Admin
- Failed
- Retrying
- Long-running

### Platform Trends

- Goal-plan acceptance
- Completion
- Replan acceptance
- Tutor quality reports
- Resource quality

### Incidents

- Security
- Integration
- Model
- Database
- Queue
- Storage

---

# 29. Admin Students List

Route: `/admin/students`

## Table Columns

- Student
- Status
- Active goals
- Goal health
- Open review items
- Open high risks
- Last activity
- Created date

## Filters

- Status
- Goal category
- Risk
- Review required
- Date
- Administrative scope

## Actions

- Open student
- Open review item
- Export permitted summary
- Suspend account with reason

Sensitive columns must be permission-controlled.

---

# 30. Admin Student Detail

Route: `/admin/students/[studentId]`

Tabs:

## Summary

- Account status
- Goals
- Progress overview
- Open review items
- Authorized risks
- Recent system actions

## Goals

- Goal list
- Plan health
- Versions
- Review actions

## Evidence

- Flagged or reviewable evidence
- Verification report
- Decision controls

## Assessments

- Flagged generated assessment
- Attempts where policy allows
- Rubric disputes

## Risks

- Evidence
- Agent confidence
- Intervention recommendation
- Admin action

## Workflows

- Runs
- Status
- Agent steps
- Safe summaries
- Retry or cancel

## Audit

- Access and state-change history

Private tutor and focus content is hidden unless a recorded policy purpose authorizes it.

---

# 31. Admin Review Queue

Route: `/admin/reviews`

## Queue Types

- Evidence uncertainty
- Integrity concern
- Unsafe or broken resource
- Assessment quality
- High-severity risk
- Goal policy
- Replan exception
- Agent low confidence
- Tool security flag

## Review Item

- Type
- Severity
- Student
- Goal
- Created time
- SLA
- Assigned Admin
- Agent recommendation
- Evidence references
- Decision history

## Review Detail

- Safe context
- Source artifacts
- Agent output
- Confidence
- Policy
- Alternatives
- Approve
- Reject
- Edit structured result
- Request Student input
- Escalate operational incident

Every action requires a reason.

---

# 32. Admin Risks

Route: `/admin/risks`

## Table

- Risk ID
- Student
- Goal
- Type
- Severity
- Confidence
- Age
- Status
- Intervention
- Review state

## Detail

- Evidence timeline
- Root causes
- False-positive indicators
- Suggested intervention
- Related workflows
- Admin decision
- Resolution

Admin UI must state that risk is not a medical or personal diagnosis.

---

# 33. Admin Agents

Route: `/admin/agents`

## Agent Registry Table

- Agent name
- Version
- Deployment
- Enabled
- Mode
- Model route
- Allowed tools
- Success rate
- Latency
- Review rate
- Last deployment

## Agent Detail

Tabs:

- Overview
- Capabilities
- Agent Card
- Input/output schemas
- Tool permissions
- Prompt
- Model route
- Evaluations
- Metrics
- Runs
- Incidents
- Versions

## Actions

- Enable or disable
- Change rollout percentage
- Promote tested version
- Roll back
- Edit budget
- Edit tool allowlist
- Run evaluation
- Test Agent Card
- Open A2A endpoint health

Production changes require confirmation and audit reason.

---

# 34. Admin Workflows

Route: `/admin/workflows`

## Table

- Workflow ID
- Type
- Student
- Goal
- Status
- Current agent
- Duration
- Retries
- Waiting reason
- Started time

## Workflow Detail

- Graph visualization
- Timeline
- Agent steps
- Input/output safe summary
- Events
- State checkpoints
- Approvals
- Errors
- Protocol calls
- Trace link

## Actions

- Retry failed activity
- Resume with decision
- Cancel
- Reassign review
- Download diagnostic bundle
- Create repair workflow

Never directly mutate workflow history.

---

# 35. Admin Knowledge Management

Route: `/admin/knowledge`

## Areas

- Competencies
- Prerequisites
- Goal templates
- Common misconceptions
- Learning objectives
- Evidence examples
- Knowledge sources

## Competency Editor

- Canonical name
- Aliases
- Description
- Category
- Proficiency levels
- Prerequisites
- Learning objectives
- Assessment methods
- Evidence requirements
- Status
- Version

## Graph Editor

- Add relationship
- Validate cycle
- Detect orphan nodes
- Preview affected goals
- Publish version

Publishing requires validation and impact report.

---

# 36. Admin Resource Management

Route: `/admin/resources`

## Table

- Resource
- Provider
- Competencies
- Difficulty
- Language
- Cost type
- Quality
- Link health
- Review date
- Status

## Resource Editor

- Metadata
- URL
- Licensing
- Accessibility
- Age suitability
- Competency mapping
- Quality notes
- Approval state
- Expiration or review date

## Actions

- Validate link
- Preview
- Approve
- Suspend
- Replace
- Merge duplicate
- Reindex
- View recommendation usage

---

# 37. Admin Assessment Management

Route: `/admin/assessments`

Tabs:

- Templates
- Question bank
- Rubrics
- Generated-review queue
- Coverage analytics

## Template Editor

- Assessment type
- Competencies
- Objectives
- Question distribution
- Difficulty distribution
- Duration
- Pass threshold
- Integrity settings
- Rubric
- Version

## Question Editor

- Prompt
- Response type
- Answer key
- Explanation
- Difficulty
- Competency tags
- Source
- Status

---

# 38. Admin Models and Prompts

Route: `/admin/models-prompts`

## Model Routes

- Logical route
- Primary provider/model
- Fallback
- Limits
- Cost
- Latency
- Availability
- Rollout
- Evaluation status

## Prompt Registry

- Agent
- Prompt ID
- Version
- Status
- Diff
- Output schema
- Allowed tools
- Evaluation score
- Approved by
- Effective date

## Actions

- Create draft
- Compare
- Run test dataset
- Promote
- Roll back
- Archive

Do not allow direct production edits without version creation.

---

# 39. Admin Analytics

Route: `/admin/analytics`

## Product Analytics

- Goal creation
- Plan acceptance
- Milestone completion
- Activity versus mastery
- Replan rate
- Recovery success
- Assessment completion
- Resource usefulness
- Tutor feedback

## Agent Analytics

- Success
- Failure
- Confidence
- Review rate
- Latency
- Cost
- Tool calls
- A2A calls
- MCP calls

## Filters

- Date
- Goal category
- Agent
- Version
- Cohort
- Administrative scope

Protect privacy through aggregation and minimum group sizes.

---

# 40. Admin Audit Logs

Route: `/admin/audit`

## Columns

- Timestamp
- Actor
- Role
- Action
- Resource
- Student
- Workflow
- Before/after
- Reason
- Trace ID
- Result

## Features

- Advanced filter
- Immutable indicator
- JSON diff
- Export
- Trace navigation
- Access-log view

---

# 41. Admin System Health

Route: `/admin/system-health`

## Services

- API
- Temporal
- NATS
- PostgreSQL
- Redis
- Neo4j
- Qdrant
- Object storage
- Model providers
- A2A agents
- MCP servers
- Notification services

## Metrics

- Availability
- Latency
- Error rate
- Queue lag
- Worker capacity
- Storage
- Database connections
- Circuit-breaker state

## Actions

- Open incident
- Disable integration
- Switch model fallback
- Drain worker
- View runbook
- Download diagnostics

---

# 42. Admin Policies

Route: `/admin/policies`

## Policy Categories

- Authorization
- Consent
- Data retention
- Academic integrity
- Student safety
- Agent budgets
- Tool permissions
- Risk thresholds
- Evidence review
- Notification limits
- Resource approval
- Model use

## Editor Requirements

- Draft and published versions
- Validation
- Impact preview
- Approval reason
- Effective date
- Rollback

---

# 43. Frontend Folder Structure

```text
astrapath-frontend/
├── package.json
├── pnpm-lock.yaml
├── next.config.ts
├── middleware.ts
├── app/
│   ├── (public)/
│   │   ├── page.tsx
│   │   └── help/
│   ├── (auth)/
│   │   ├── login/
│   │   ├── register/
│   │   ├── forgot-password/
│   │   └── verify-email/
│   ├── student/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── onboarding/
│   │   ├── goals/
│   │   ├── today/
│   │   ├── calendar/
│   │   ├── focus/
│   │   ├── tutor/
│   │   ├── assessments/
│   │   ├── evidence/
│   │   ├── progress/
│   │   ├── mastery/
│   │   ├── portfolio/
│   │   ├── resources/
│   │   ├── notifications/
│   │   ├── settings/
│   │   └── help/
│   ├── admin/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── students/
│   │   ├── reviews/
│   │   ├── risks/
│   │   ├── agents/
│   │   ├── workflows/
│   │   ├── knowledge/
│   │   ├── resources/
│   │   ├── assessments/
│   │   ├── models-prompts/
│   │   ├── analytics/
│   │   ├── audit/
│   │   ├── system-health/
│   │   ├── policies/
│   │   └── settings/
│   ├── api/
│   ├── error.tsx
│   ├── not-found.tsx
│   └── layout.tsx
├── components/
│   ├── ui/
│   ├── layout/
│   ├── goals/
│   ├── roadmap/
│   ├── milestones/
│   ├── planning/
│   ├── focus/
│   ├── tutor/
│   ├── assessments/
│   ├── evidence/
│   ├── progress/
│   ├── mastery/
│   ├── resources/
│   ├── agents/
│   ├── workflows/
│   ├── admin/
│   └── feedback/
├── features/
│   ├── auth/
│   ├── student-profile/
│   ├── goals/
│   ├── daily-plan/
│   ├── focus/
│   ├── tutor/
│   ├── assessments/
│   ├── evidence/
│   ├── progress/
│   ├── mastery/
│   ├── admin-review/
│   ├── agent-operations/
│   └── system-health/
├── lib/
│   ├── api/
│   │   ├── generated/
│   │   ├── client.ts
│   │   ├── errors.ts
│   │   └── query-keys.ts
│   ├── auth/
│   ├── streaming/
│   ├── validation/
│   ├── telemetry/
│   ├── dates/
│   ├── permissions/
│   └── utilities/
├── stores/
├── hooks/
├── providers/
├── styles/
├── public/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── accessibility/
│   └── e2e/
└── stories/
```

---

# 44. API Client Strategy

Generate TypeScript types and API functions from backend OpenAPI.

```typescript
export async function createGoal(
  body: CreateGoalRequest,
  signal?: AbortSignal,
): Promise<AcceptedWorkflowResponse> {
  const response = await apiClient.post("/v1/student/goals", {
    body,
    signal,
  });

  if (!response.ok) {
    throw await ApiError.fromResponse(response);
  }

  return response.json();
}
```

## Query Key Rules

```typescript
export const queryKeys = {
  student: {
    profile: ["student", "profile"] as const,
    dashboard: ["student", "dashboard"] as const,
    goals: (filters: GoalFilters) => ["student", "goals", filters] as const,
    goal: (goalId: string) => ["student", "goal", goalId] as const,
  },
  admin: {
    students: (filters: AdminStudentFilters) =>
      ["admin", "students", filters] as const,
    workflow: (id: string) => ["admin", "workflow", id] as const,
  },
};
```

---

# 45. Real-Time Workflow Client

```typescript
type WorkflowEvent = {
  id: string;
  type: "agent_status" | "input_required" | "approval_required" | "completed" | "failed";
  workflowId: string;
  agent?: string;
  progress?: number;
  summary?: string;
};

export function subscribeToWorkflow(
  workflowId: string,
  onEvent: (event: WorkflowEvent) => void,
): () => void {
  const stream = new EventSource(`/v1/workflows/${workflowId}/events`, {
    withCredentials: true,
  });

  stream.onmessage = (message) => {
    onEvent(JSON.parse(message.data));
  };

  stream.onerror = () => {
    // EventSource reconnects automatically.
  };

  return () => stream.close();
}
```

## Streaming UI Requirements

- Reconnect with last event ID
- Avoid duplicate event rendering
- Show stale-connection state
- Allow cancel where backend permits
- Refetch final read model after completed event
- Never infer completion only from client progress

---

# 46. Frontend State Management

## TanStack Query

Use for:

- Profiles
- Goals
- Plans
- Tasks
- Assessments
- Evidence
- Progress
- Mastery
- Admin tables
- Workflow read state

## Zustand

Use only for:

- Sidebar state
- Goal switcher state
- Focus-session local controls
- Draft composer state
- Temporary graph view state
- Command palette

## URL State

Use for:

- Table filters
- Sort
- Date range
- Selected tab
- Search
- Pagination

---

# 47. Form Architecture

Use React Hook Form and Zod.

```typescript
const goalSchema = z.object({
  goalStatement: z.string().min(10).max(2000),
  targetDate: z.string().date().optional(),
  priority: z.enum(["low", "medium", "high"]),
  weeklyMinutes: z.number().int().min(30).max(10080),
});
```

Requirements:

- Field-level errors
- Server error mapping
- Autosave for long wizards
- Dirty-state warning
- Accessible error summary
- Retry without re-entering values
- Never log sensitive field values to analytics

---

# 48. Loading, Empty, Error, and Offline States

Every page must define:

## Loading

- Skeleton matching final layout
- Preserve navigation
- Show workflow status when known

## Empty

- Explain why it is empty
- Provide one primary action
- Avoid dead ends

## Error

- Human-readable message
- Retry
- Support reference ID
- Preserve safe draft state
- Do not show raw stack trace

## Offline

- Connection banner
- Read cached non-sensitive data
- Queue only safe local drafts
- Do not claim server action succeeded
- Reconcile after reconnect

---

# 49. Accessibility

Target WCAG 2.2 AA.

Requirements:

- Full keyboard navigation
- Visible focus
- Skip links
- Semantic headings
- Form labels
- Error summary
- Screen-reader status regions
- Reduced motion
- Color-independent status
- Chart table alternatives
- Captions or transcripts
- Timer announcements at user-selected intervals
- Accessible graph list representation
- Minimum touch target size
- Avoid time limits unless required; allow extensions where policy permits

---

# 50. Frontend Security

- Use secure HTTP-only session cookies.
- Apply CSRF protection to state-changing requests.
- Escape rendered Markdown.
- Sanitize rich text.
- Restrict iframe and external content.
- Use strict Content Security Policy.
- Validate file type and size client-side and server-side.
- Never rely on hidden UI as authorization.
- Use route middleware only as convenience; backend remains authoritative.
- Redact private data from client logging.
- Protect Admin actions with re-authentication where required.
- Add confirmation for destructive or production-impacting actions.

---

# 51. Performance

- Stream page shells.
- Lazy-load graphs, editors, charts, and calendar.
- Virtualize long Admin tables.
- Paginate audit and workflow data.
- Use image optimization.
- Cache safe server reads.
- Avoid rendering every tutor token as a separate React state update.
- Debounce search.
- Prefetch likely next Student page.
- Use bundle analysis.
- Set performance budgets.

Suggested budgets:

- Core Student page JavaScript: under agreed product threshold
- Interaction response: immediate feedback under 100 ms
- Main content usable quickly on average mobile network
- Large graph/editor loaded only on demand

---

# 52. Testing Strategy

## Unit

- Utilities
- Zod schemas
- Permission helpers
- State stores
- Data transformers
- Progress calculations displayed by UI

## Component

- Task card
- Approval card
- Agent activity
- Tutor message
- Evidence review
- Admin decision form
- Graph node drawer

## Integration

- Form and API error mapping
- SSE events
- File upload
- Authentication redirect
- Role protection
- Query invalidation

## End-to-End Student

- Register and onboard
- Create goal
- Respond to clarification
- Complete diagnostic
- Approve plan
- Start focus session
- Ask Tutor
- Complete assessment
- Upload evidence
- View mastery
- Approve replan

## End-to-End Admin

- Sign in
- Open review queue
- Review evidence
- Inspect workflow
- Disable broken resource
- Promote prompt version
- View audit log
- Handle agent failure

## Accessibility

- Automated axe checks
- Keyboard-only flows
- Screen-reader smoke tests
- Contrast review
- Reduced-motion review

---

# 53. Storybook Coverage

Create stories for:

- All statuses
- Empty states
- Error states
- Long content
- Mobile width
- Dark mode if supported
- Reduced motion
- Student and Admin variants
- High-risk review item
- Agent streaming
- Workflow waiting state

---

# 54. Frontend Implementation Phases

## Phase 1 — Foundation

- Next.js project
- Design tokens
- Authentication
- Student/Admin layouts
- API client
- Query provider
- Error handling
- Core components

## Phase 2 — Student Goal Planning

- Onboarding
- Dashboard
- Goals list
- Goal wizard
- Goal detail
- Agent status streaming

## Phase 3 — Daily Execution

- Today
- Calendar
- Focus
- Notifications

## Phase 4 — Learning

- Tutor
- Resources
- Assessments
- Results
- Evidence

## Phase 5 — Intelligence Views

- Progress
- Mastery
- Risks
- Replan approval
- Portfolio

## Phase 6 — Admin Operations

- Admin dashboard
- Students
- Review queue
- Risks
- Workflows
- Agents

## Phase 7 — Admin Governance

- Knowledge
- Resources
- Assessments
- Models and prompts
- Policies
- Audit
- System health
- Analytics

## Phase 8 — Hardening

- Accessibility
- Performance
- Security
- E2E tests
- Cross-browser
- Responsive refinement
- Observability

---

# 55. Page Completion Checklist

A page is complete only when it has:

- Role and permission checks
- Desktop and mobile design
- Loading state
- Empty state
- Error state
- Offline behavior
- API integration
- Analytics events with privacy review
- Accessibility review
- Unit/component tests
- E2E coverage for critical paths
- Audit behavior for Admin actions
- Agent workflow status where applicable
- Confirmation for high-impact actions
- Product copy reviewed for supportive tone

---

# 56. Final Frontend Recommendation

Build the Student experience first around one complete path:

```text
Onboarding
→ Create Goal
→ Agent Workflow Progress
→ Diagnostic
→ Plan Approval
→ Today
→ Focus
→ Tutor
→ Assessment
→ Evidence
→ Progress
→ Replan
```

Then build the Admin path:

```text
Dashboard
→ Review Queue
→ Student Context
→ Evidence/Risk Review
→ Workflow Inspection
→ Agent and Knowledge Governance
→ Audit and System Health
```

This structure keeps the application focused on the only two roles—Student and Admin—while making the 20-agent backend understandable, controllable, and visible through a polished product experience.

---

# 57. Official Frontend References

- Next.js App Router: https://nextjs.org/docs/app
- TanStack Query: https://tanstack.com/query/latest/docs/react/overview
- Zustand: https://zustand.docs.pmnd.rs/
- React Hook Form: https://react-hook-form.com/
- Tailwind CSS: https://tailwindcss.com/docs
- Radix UI: https://www.radix-ui.com/primitives/docs/overview/introduction
- Playwright: https://playwright.dev/docs/intro
- WAI accessibility resources: https://www.w3.org/WAI/
