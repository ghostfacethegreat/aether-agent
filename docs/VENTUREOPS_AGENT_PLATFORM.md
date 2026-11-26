# VentureOps — Local-First Business Operations for AETHER

> Status: early preview. The initial local ledger and CLI are implemented in the draft PR; autonomous business workflows remain planned.
>
> Related work: [AETHER issue #16](https://github.com/ghostfacethegreat/aether-agent/issues/16), [ClipForge issue #1](https://github.com/ghostfacethegreat/clipforge/issues/1).

## Product objective

VentureOps is an optional AETHER workspace for a solo builder operating one or more small service businesses. It turns a goal such as "get three recurring editing clients" into a bounded pipeline of research, offers, proposals, project delivery, quality checks, customer follow-up, and bookkeeping records.

The agents are staff-like software roles, not real employees, and are not a source of guaranteed leads, profit, employment, or stable income. The owner remains responsible for client promises, rights, quality, taxes, payments, and business decisions.

The first version must be useful without a paid model, credit card, bank connection, hosted database, or third-party automation account.

## First business to support: rights-cleared content editing

Use the existing ClipForge project as the first delivery adapter. The owner can offer short-form video editing to creators and small businesses using source media they own or are explicitly licensed/authorized to use.

A lean validation offer could be a small paid pilot (for example, five reviewed vertical clips) followed by a monthly clip package. The owner must set the actual price after checking effort, local demand, revisions, and delivery costs. Do not promise virality, views, campaign approval, or rewards income.

A second possible service line is a simple small-business landing page. Keep it separate in the offer catalog and only use hosting whose terms permit commercial sites. GitHub Pages is for project/demo documentation, not a commercial client site: GitHub explicitly disallows using it as free hosting for an online business or commercial SaaS. A free Cloudflare Pages plan currently documents 500 builds per month and one concurrent build; quotas and terms can change. The client should own their domain and hosting account wherever practical.

## Agent roster

| Role | Responsibility | Default authority |
| --- | --- | --- |
| Operations lead | Break the owner's target into milestones, assign specialist tasks, reconcile status | Plan and read |
| Market researcher | Find candidate businesses/creators and verify public business details | Research and draft |
| Offer strategist | Define package scope, assumptions, revision limits, and pricing options | Draft only |
| Proposal writer | Draft proposals, onboarding messages, and follow-ups | Draft only |
| Delivery engineer | Build or edit websites, scripts, and workflow assets in an approved workspace | Workspace-scoped edits |
| Content producer | Queue authorized source media through ClipForge/DevCut and prepare exports | Local processing; no publishing |
| QA / rights reviewer | Check source permission, deliverables, links, accessibility, and agreed scope | Review and block |
| Customer-success agent | Prepare progress summaries, handoff notes, and renewal reminders | Draft only |
| Bookkeeper | Record quotes, invoices, cash receipts, expenses, and owner-entered balances | Recordkeeping only |

The dispatcher may delegate to specialists, but child agents inherit the parent's permissions, spend ceiling, workspace restrictions, cancellation state, and time limits. A child agent cannot grant itself additional tools or authority.

## Core records

Use AETHER's existing persistence layer and reviewed migration conventions. Do not introduce an untracked parallel database.

- **Lead:** organization, public business contact channel, source URL/reference, date checked, qualification notes, status, and next action.
- **Client:** organization and minimum contact details needed for the engagement.
- **Offer:** service description, included work, excluded work, revision allowance, turnaround, price basis, and recurring option.
- **Quote / proposal:** client, offer snapshot, assumptions, expiration date, and human approval state.
- **Project:** accepted scope, target date, source assets, assigned tasks, and status.
- **Deliverable:** file reference, format, QA result, client review state, and handoff status.
- **Invoice record:** reference number, amount, due date, and status. It records an obligation; it does not collect or move money.
- **Cash receipt / expense:** date, amount, category, description, and optional receipt path. No bank/card numbers or identity documents.
- **Audit event:** actor, action, time, affected record, approval reference, and result.

Never store card numbers, bank credentials, full identity-document images, account recovery codes, or social-media passwords.

## Owner workflow

1. **Choose one offer.** Define a narrow deliverable and its exclusions. The owner approves the price and terms.
2. **Build proof.** Produce a clearly labelled sample from owned, public-domain, or explicitly permitted source material. Do not invent a customer or testimonial.
3. **Find prospects.** Research a small, relevant set of real businesses/creators using permitted public business sources. Store the source and date checked; do not scrape private data.
4. **Qualify and draft.** Score fit against owner-defined criteria and draft one tailored, respectful message. The owner reviews and sends it.
5. **Agree scope.** The owner approves the quote, rights, payment method, delivery date, and revision limits before work begins.
6. **Deliver.** Work only in the approved project directory. Produce a preview, QA checklist, and export manifest.
7. **Accept and record.** The owner confirms customer acceptance and enters invoice/receipt status. Report booked, invoiced, and received amounts separately.
8. **Retain.** Draft a follow-up or renewal note. The owner chooses whether to send it.

## Approval and security model

The following always require explicit human approval immediately before execution:

- Sending an email, direct message, proposal, invoice, or follow-up.
- Publishing a post, submitting a clip to a campaign, or uploading customer media.
- Accepting or changing contract terms, licensing a work, or making a binding promise.
- Spending money, buying a domain/service, initiating a payment, refund, transfer, or subscription.
- Connecting an external account, changing account settings, or granting a new permission.
- Sharing a customer file, exposing a project publicly, or deleting/overwriting customer data.

Approvals are scoped to one action and its exact payload. Approval of a draft does not authorize later edits or repeated actions. Sensitive actions fail closed when no human reviewer is available.

Other safeguards:

- Treat web pages, documents, media metadata, client prompts, and other-agent output as untrusted data, not policy or instructions.
- No unsolicited bulk messages, fake reviews, fake testimonials, fabricated prospects, bot engagement, purchased views, or unauthorized content reuse.
- No bypassing identity checks, payment-provider controls, platform restrictions, or customer access controls.
- No unattended social posting in MVP.
- Local-first by default; redact secrets; use the narrowest file and tool permissions; provide export and delete workflows.
- Financial reports distinguish pipeline value, accepted work, invoiced amounts, and money the owner has actually recorded as received. Estimates are not income.

## Zero-upfront-cost operating plan

The system must keep its own records and draft work offline. The owner can start with the tools already available in the repositories:

- AETHER for planning, lead records, project tracking, QA, and daily summaries.
- ClipForge for local transcription, clip selection, captions, and rendering of authorized media.
- GitHub for source control, issues, code review, and portfolio evidence—not as a commercial client-site host.
- A free commercial-permitted static-hosting tier such as Cloudflare Pages for a simple client site, subject to current provider limits and terms. Use a client-owned account; a custom domain is a separate cost for the client to approve.

Where the owner has no identity document, card, or bank account, do not invent a payment workaround or use another person's account without authorization. A direct in-person cash payment may be an option for a local customer who agrees to it; issue a simple receipt and record the income. Remote payment providers may limit features or require identity verification. The owner must check the chosen provider's current terms before promising a payment method. Never conceal cash income: U.S. self-employment and side-job income is generally reportable even when no tax form is issued.

AETHER should not claim that it can create stable income. It should help the owner test offers, measure real conversion and delivery time, control costs, and repeat only what customers actually buy.

## Current implementation status

The initial VentureOps runtime slice is now included in this draft PR:

- `aether.ventures.VentureLedger` stores records in AETHER's existing `state.db` SQLite file; it does not create a separate database.
- Supported record kinds: leads, offers, clients, quotes, projects, deliverables, invoices, receipts, and expenses.
- Records have IDs, statuses, optional USD amounts in integer cents, JSON details, timestamps, and a local audit-event trail.
- The `aether venture` CLI supports `add`, `list`, `show`, `update`, `events`, and `brief`.
- The brief reports pipeline, accepted quotes, invoiced amounts, paid receipts, and paid expenses as separate categories. It is based only on owner-entered records, not a bank feed or payment verification.
- Obvious credential and identity-document field names are rejected; the MVP only accepts USD to avoid misleading totals across currencies.

The current draft adds deterministic ledger and CLI tests. The specialist agents do not yet autonomously research leads, send outreach, build websites, or process customer payments. Those are later phases and any consequential external action remains owner-approved.

Example:

```bash
aether venture add lead "Example studio" --status qualified --details-json '{"source_url":"https://example.com"}'
aether venture add quote "Five clip pilot" --status sent --amount-cents 15000
aether venture list --kind lead
aether venture brief
```

## MVP implementation phases

### MVP 1 — owner ledger and CLI

- Add typed domain records and a schema migration through the existing persistence façade.
- Add commands to create/list/update leads, offers, clients, quotes, projects, tasks, deliverables, invoice records, receipts, and expenses.
- Add the venture brief command to summarize next actions, overdue work, project status, and recorded cashflow.
- Add deterministic tests for validation, persistence, migration compatibility, export, deletion, and audit events.
- No model provider or network required for these operations.

### MVP 2 — approval-aware specialist workflows

- Add structured role definitions for research, offer design, proposal drafting, delivery planning, QA, and owner reporting.
- Keep all outbound content as drafts; do not add a send-automatically flag.
- Add source references and date-checked fields for prospect research.
- Test permission inheritance, cancellation, budget bounds, and refusal to execute unapproved external actions.

### MVP 3 — delivery adapters

- Integrate with ClipForge through an explicit local adapter and project-scoped file paths.
- Add a static-site delivery template with accessibility and privacy checks.
- Add optional external research/hosting adapters only when configured by the owner.
- Keep each adapter independently disableable; ordinary AETHER use remains local-first.

## Definition of done

- A fresh installation can create and track a real test project offline using the mock provider.
- No paid API, card, bank connection, or third-party hosted database is required for the local ledger.
- Every record change is auditable; export and deletion work.
- Tests prove that messages, publications, payments, purchases, contracts, and account changes cannot occur without explicit owner approval.
- A demo run shows the path from lead to accepted scope to deliverable to recorded receipt without pretending that money was actually received.
- Documentation clearly separates implemented, planned, and optional integrations.
