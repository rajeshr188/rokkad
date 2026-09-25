---
status: awaiting-owner-selection
owner: project
updated: 2026-09-25
tags: [product, marketing, landing-page, mockups]
---

# Landing page: explicit SaaS positioning

The owner clarified that Rokkad sells a **loan management SaaS product**. The
landing page must state this explicitly alongside the borrower-to-release story.
Our current supported audience is pawn-lending businesses, including gold and
silver lending. Do not broaden the positioning into unsupported lending sectors.

The owner requested mockups and will select the production direction. **No
production landing-page change is approved by this design-review request.**
The currently deployed application remains `67be05b5`.

## Concepts for review

The [interactive source](landing-page-mockups.html) is a self-contained
conversation preview with three switchable concepts. It is not an application
template or production route. Its decorative icons use the conversation's
provided Lucide runtime; text and layout remain readable without those icons.

| Concept | Main emphasis | What the customer sees first |
|---|---|---|
| A: Product first | Software category and practical capability | Loan management software, its pawn-lending audience, and an illustrative loan list |
| B: Journey first | Customer trust and physical pledge | Explicit SaaS category above an editorial borrower-to-return story |
| C: Business first | Owner and counter operations | Cloud loan management SaaS and the working day it supports |

All concepts include subscription/browser positioning, staff roles, separate
workspaces, lending/collection/custody capabilities and a clear next-step CTA.
Account setup and sign-in controls are local preview interactions. Sample loan
records are invented and labelled; there are no real customer records, fabricated
testimonials, promised returns, pricing claims or automatic migration promises.
Assisted migration is distinguished from planned guided Excel loan import.

## Selection and implementation boundary

Await the owner's choice of A, B, C or a deliberate combination. A is the initial
recommendation because the product category is unmistakable before the story.
The preview also allows comparing "software" versus "SaaS" in A's headline and
compact hero spacing. These are presentation experiments, not production settings.

After selection, adapt the selected direction into the existing Django public
template, reuse real sign-up/sign-in routes and the production design system,
retain truthful capability boundaries, and perform responsive/accessibility checks.
Do not deploy the concept switcher as a customer-facing feature.

Related: [implemented loan journey](../flows/loan-journey.md) and
[guided legacy migration backlog](future-work.md#fw-007-guided-customer-facing-legacy-migration).
