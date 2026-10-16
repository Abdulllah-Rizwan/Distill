# Distil Constitution

Distil is a solo-built, AI-powered "second brain" for students: it ingests their notes, maps the
concepts into a knowledge graph, and surfaces the vital few (80/20) ideas with an explainable
ranking. This constitution governs how it is built. Its second purpose is explicit: the author is
building Distil to become a better engineer, so the document favors deliberate, documented,
understood decisions over speed.

## Core Principles

### I. Source-Faithfulness (NON-NEGOTIABLE)
Every concept, graph edge, ranking, and generated artifact MUST trace back to material the user
uploaded. The system MUST NOT assert facts that are not grounded in the user's own notes, and MUST
NOT silently enrich with outside knowledge. Where a claim cannot be grounded, the system MUST
surface uncertainty rather than fabricate.
Rationale: A study tool that teaches a confidently wrong fact is worse than no tool, because the
student memorizes the error. Trust in the source is the product.

### II. Explainable Intelligence
Every AI-produced output — graph relationships and the 80/20 ranking above all — MUST carry a
visible, source-linked "why." The 80/20 ranking MUST be grounded in graph-derived signals (e.g.
concept centrality and recurrence across materials) used as the evidence, with the model acting as
ranker and explainer over concepts actually extracted from the user's material. Black-box scores
with no stated reason are prohibited.
Rationale: An unexplained ranking cannot be trusted or corrected, and it collides with Principle I;
a visible rationale is what makes the 80/20 claim real instead of marketing.

### III. Documented Decisions (ADRs)
Every significant architecture or technology-stack decision MUST be recorded as an Architecture
Decision Record capturing: the context, the options considered, the decision, and the rationale.
A dependency, framework, or pattern MUST NOT be adopted without such a record.
Rationale: This is the project's learning engine made mandatory. The author grows by reasoning
decisions through and leaving a trail, and future-self can revisit why a path was chosen.

### IV. Understand Before Adopt
No dependency, pattern, or generated code enters the codebase that the author cannot explain in
their own words. AI-assisted code is reviewed and understood before it is committed; the human
stays in the loop on every design decision. Copy-paste-until-it-works is prohibited.
Rationale: The goal is to become an engineer, not a vibe coder. Code you cannot explain is code you
cannot debug, secure, or evolve.

### V. Privacy & Data Stewardship
Student coursework is sensitive and MUST be treated as such. Each user's or group's workspace MUST
be isolated; data MUST NOT leak across workspaces. Secrets MUST NOT be committed to source control.
User-uploaded material MUST NOT be used for any purpose the user did not ask for (including model
training) without explicit consent.
Rationale: Students entrust the platform with their academic work; mishandling it is both an ethical
and a trust failure that no feature can offset.

### VI. Simplicity that Ships
Each feature MUST start with the simplest design that serves a real user end-to-end. Speculative
abstraction, configuration, or infrastructure for unspecified future needs is prohibited (YAGNI).
Added complexity MUST be justified against a concrete requirement, and ideally captured in an ADR.
"Works in a demo" is not "works"; v1 must function for an actual student, not just a happy path.
Rationale: A solo builder's scarcest resource is attention; simplicity is what makes shipping to a
real customer achievable and the system auditable against these principles.

### VII. Verified Reliability — Tested & Evaluated
Reliability MUST be measured, not assumed:
- Deterministic logic — ingestion/parsing, graph construction, API contracts, authentication and
  workspace isolation — MUST have automated tests. Anything whose breakage would harm a user MUST
  be tested before it is trusted.
- Every AI capability (concept extraction, edge creation, 80/20 ranking) MUST be measured by an
  eval suite against a curated dataset, scoring at minimum faithfulness (no ungrounded claims) and
  relevance.
- Any prompt, model, or pipeline change MUST run against the eval suite before merge; a regression
  in faithfulness blocks the change.
- Every faithfulness failure found in real use MUST become a new eval case so it cannot silently
  regress again.
Rationale: Principles I and II are promises; with a non-deterministic LLM in the loop, tests and
evals are the only way to know those promises still hold as the system changes.

### VIII. Senior-Grade Code Quality
Code MUST be written to a professional, senior-engineer standard. Concretely: it MUST be modular
and cohesive, with a clear separation of concerns; it MUST follow sound practices (meaningful names,
small focused functions, no needless duplication, errors handled deliberately); and it MUST apply
consistent, intentional design patterns across the codebase rather than ad-hoc one-offs, so that the
system reads as one coherent whole. Where a pattern would add ceremony or abstraction that does not
serve clarity, Principle VI (Simplicity that Ships) prevails — quality here means code that is
modular, readable, and explainable, never gold-plating.
Rationale: The author is building Distil to become a strong engineer, so the habits formed in this
codebase are themselves a goal (see Principle IV). Beyond that, well-structured and consistent code
is cheaper to debug, secure, test, and evolve, and it is a precondition for the faithfulness and
reliability the other principles demand — unmaintainable code cannot be kept trustworthy.

## AI Quality & Data Standards

The eval dataset is a first-class, versioned project asset, maintained alongside the code. Faithfulness
is the primary eval metric and takes precedence over fluency or coverage when they conflict. AI
outputs presented to users MUST expose their grounding (source references) so a user can verify a
claim. Prompts and model/version choices MUST be recorded (an ADR for the choice; the prompt in
source control) so behavior changes are traceable. User data MUST be isolated per workspace at the
storage and query layer, encrypted in transit (TLS outside local development), and secrets supplied
via environment or a secrets manager — never hard-coded.

## Development Workflow

Work flows through the Spec Kit lifecycle: specify → plan → tasks → implement, with clarify and
analyze used as needed. Because the project is solo-built, governance relies on self-discipline
rather than peer sign-off:
- Every change is self-reviewed against this constitution before merge; a violation is either fixed
  or recorded as an explicit, justified exception (and, if architectural, an ADR).
- Significant decisions produce an ADR (Principle III) before the code that depends on them lands.
- Deterministic tests and the relevant AI evals (Principle VII) MUST pass before a change is
  considered done; a faithfulness regression blocks the change.
- The main branch MUST remain releasable: tests and evals green, no known unresolved constitution
  violations.

## Governance

This constitution supersedes other development practices where they conflict. Amendments MUST be
proposed in writing by the author, recorded (as an ADR when they change how the project is built),
and accompanied by a version bump and a note on any migration required.

Versioning follows semantic versioning: MAJOR for backward-incompatible governance or principle
removals/redefinitions, MINOR for a newly added principle or materially expanded section, PATCH for
clarifications and non-semantic wording fixes.

Compliance is self-reviewed on every change. Complexity that appears to violate Principle VI MUST be
justified or removed. The two load-bearing guarantees — Source-Faithfulness (I) and Verified
Reliability (VII) — are never waived: a change that cannot demonstrate faithfulness does not ship.

**Version**: 1.1.0 | **Ratified**: 2026-10-15 | **Last Amended**: 2026-10-16
