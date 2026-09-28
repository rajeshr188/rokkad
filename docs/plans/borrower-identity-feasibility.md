---
status: shelved
owner: project
updated: 2026-09-26
tags: [plans, party, identity, feasibility]
related: [future-work.md, ../domain/party.md, ../architecture/control-plane-contracts.md]
---

# Borrower identity verification: feasibility review

## Outcome and scope

**Shelved at owner request on 2026-09-26.** Resume only when the owner explicitly
reopens FW-009. The deferred next step is identifying the contracting legal entities
and obtaining written eligibility/hosting answers and quotes before selecting an
integration for a small pilot. The recommendations below are retained for later;
do not initiate outreach, registration or implementation while shelved. Recheck
requirements and prices when resumed.

Desk review completed on 2026-09-26 for FW-009. The owner approved investigation
and the potential promise, **"Verify customer identity and reduce manual entry."**
Technical integration is plausible; eligibility for Rokkad's multi-lender business
model and an all-in commercial quote remain unconfirmed. This is a proposed path,
not an accepted implementation architecture or a claim of regulatory KYC compliance.
No provider accounts, applications, paid services, real identity tests or external
communications were initiated. Production and customer data were not accessed.

**Recommendation:** investigate a registered-lender Aadhaar app credential-sharing
flow first, with Rokkad acting only in a confirmed permitted software role. Compare
one provider-hosted DigiLocker issued-document journey as the alternative if it
can lawfully support our independent lenders with less onboarding effort. Choose
one route for an in-branch pilot after written eligibility and cost confirmation.
Retain a non-Aadhaar staff-review option. Do not build direct UIDAI online
authentication, biometrics or a general identity platform as the first increment.

This ranking is a product/engineering judgment: app-based selective sharing fits
minimal collection, while a hosted provider may reduce implementation work. Neither
route has yet been demonstrated with Rokkad or approved for its business model.

## What the official evidence establishes

| Finding | Consequence for this project | Evidence |
| --- | --- | --- |
| UIDAI lists selective credential sharing and optional offline face verification in its OVSE offering. Its registration page requests a callback URL, domain and certificate, among other details. | A web integration is a credible candidate; app availability and onboarding effort must be tested. Do not assume we must build a mobile app. | [UIDAI OVSE](https://uidai.gov.in/hi/ovse) |
| Regulation 13A, inserted in December 2025, specifies registration for the described paperless offline e-KYC / app credential-verification methods and allows UIDAI to determine registration and transaction charges. | Treat eligibility and fees as questions to resolve, not assume that offline means unrestricted or free. Exact applicability to a proposed QR/XML deployment needs confirmation. | [Published amendment, English pp. 5-6](https://backend.uidai.gov.in/get/files/media/document/2026-06/Regulation.pdf) |
| UIDAI's OVSE FAQ says verification cannot be performed on behalf of another entity. | Obtain written clarification for lender-owned registrations and Rokkad-hosted processing. Do not use one Rokkad account to verify borrowers for unrelated lenders by assumption. | [UIDAI OVSE FAQ](https://uidai.gov.in/hi/ovse) |
| Offline XML is digitally signed and contains demographic details; phone/email are hashes. | Authenticity checks and field extraction are feasible. Obtain a usable phone separately; never promise to retrieve it from XML. | [UIDAI offline e-KYC](https://www.uidai.gov.in/en/about-uidai/307-english-uk/faqs/aadhaar-online-services/aadhaar-paperless-offline-e-kyc.html) |
| UIDAI's current catalog lists Circular 9 of 2026 on Sub-AUA/Sub-KUA LITE. | Ask an authorised online provider whether this affects eligibility/costs. The circular's substantive terms were not retrieved in this review; its title is not evidence that Rokkad qualifies. | [Authentication documents](https://old.uidai.gov.in/hi/authentication-documents) |

Sources have differing update dates. The published December 2025 amendment and
current UIDAI requirements take precedence over older vendor explanations. The
consolidated regulation URL in FW-009 could not be parsed by the web reader; the
published amendment above was retrieved. Obtain the complete current rules and
the proposed contractual arrangement before a legal/operational go-ahead.

## Option comparison

Experience and engineering effort below are estimates, not measured pilot results.

| Route | Borrower and staff experience | Main dependency | Assessment |
| --- | --- | --- | --- |
| Aadhaar app selective credential sharing | Borrower uses the official app to consent/share; staff reviews returned fields and presenter evidence. First-time app setup adds effort. | Eligible verifier registration, permitted hosting and an agreed field/retention contract. | Preferred first eligibility enquiry; best conceptual fit for minimal sharing. |
| Signed Secure QR / offline XML | QR scanning can suit a physical counter; XML download, share code and upload are more cumbersome. A photograph of a card or OCR is not signature verification. | Method-specific permission, current signature/trust specifications, safe parsing and presenter matching. | Evaluate as a supported fallback; do not implement all formats at once or bypass registration through a file upload. |
| Provider-hosted DigiLocker issued-document sharing | Borrower completes provider/DigiLocker consent on their own device or a private customer-facing screen; staff reviews returned evidence. Account recovery/OTP can interrupt the journey. | Provider must accept the actual lender/platform structure and document who requests, receives and stores data. | Credible alternative; official issued documents must be distinguished from user-uploaded scans. Not synonymous with direct UIDAI online e-KYC. |
| Online Aadhaar authentication/e-KYC through an authorised arrangement | Customer completes the supported authentication; demographic retrieval depends on the actual authorised service. | Eligibility, KUA/Sub-KUA arrangements, contracts and ongoing obligations. Yes/no authentication alone does not populate a profile. | Defer unless the simpler candidates fail a concrete need; investigate current LITE terms rather than assuming online is impossible. |
| Staff reviews alternative identification | Existing customer record can still be created; staff records what was checked. | Agreed lender procedure and accurate labels. | Preserve as an alternative; never give it an automated source-verification badge. |

The Aadhaar app itself has a setup flow involving a smartphone, SIM selection and
face authentication. That is customer activity in the official app, not a proposed
Rokkad biometric collection flow. [UIDAI app FAQs](https://www.uidai.gov.in/en/faq)

## Bounded provider shortlist and costs

These are candidates for enquiries, not endorsements or verified eligibility.

| Candidate | Public capability evidence | What remains unverified |
| --- | --- | --- |
| Direct UIDAI OVSE arrangement | Official registration and app integration requirements above. | Which legal entity registers, permitted SaaS processor role, fee schedule, onboarding duration and testing access. |
| Digio | Published integration guides describe DigiLocker workflows and offline KYC workflows. | Independent pawn-lender eligibility, each lender's registration/contract, necessary-only fields, retention/deletion and all-in price. |
| Cashfree Secure ID | Public DigiLocker offering describes consented document retrieval and a hosted user journey. | The same legal/contractual points, onboarding and pricing; no assumption that its payment products are needed. |

Capability sources: [Digio DigiLocker integration](https://documentation.digio.in/digikyc/digilocker/integration_guide/),
[Digio offline integration](https://documentation.digio.in/digikyc/aadhaar_offline/integration_guide/),
[Cashfree DigiLocker](https://www.cashfree.com/digilocker-api/).
Digio's default Aadhaar/PAN template should not imply collection of PAN when the
chosen purpose needs only identity/address. Seek a minimal custom scope.
Provider marketing claims of universal compliance or no additional licences are
not a legal determination for Rokkad's lenders.

**Verified pricing reference:** UIDAI Circular 15 of 2025 lists, from 1 November
2025, INR 3.60 for successful e-KYC and INR 0.60 for failed e-KYC in the stated
non-telecom KUA/Sub-KUA category, inclusive of taxes. Its yes/no rate is INR 0.60.
These are upstream authentication charges, not an all-in provider quote and not
the price of an offline or DigiLocker check.
[UIDAI fee circular](https://uidai.gov.in/images/Circular_15_of_2025_08122025revised_Pricing_wef_Nov_2025.pdf)

For illustration only, 1,000 charged successful online e-KYC checks and 100 charged
failures at those rates total INR 3,660 in that component. Add any applicable
registration, provider, minimum-commitment, support and infrastructure costs.
Confirm what constitutes a chargeable failed/cancelled/retried attempt.

No reliable public all-in quote for our exact use case was established. Do not
budget the feature as free or advertise an INR-per-customer price yet. Request
quotes at 100, 1,000 and 10,000 completed verifications/month, including setup,
per-lender fees, minimums, retries, consent abandonment, SMS, evidence retrieval,
deletion, taxes and support. Measure cost per completed customer, not only API call.
Repeated loan creation should not automatically trigger another paid identity check;
define refresh conditions from the selected method and lender requirements.

## Recommended first customer journey

1. From a Party profile or customer creation, authorized staff selects **Verify
   customer**. Explain lender identity, purpose, requested fields, retention and
   alternative route in clear borrower-facing language.
2. Create a short-lived request bound to the Workspace, Party/draft customer and
   initiating actor. The borrower completes the agreed official/provider flow.
   Staff must not ask the borrower to disclose an OTP or PIN to them.
3. Validate response authenticity, request binding and freshness. Show the evidence
   alongside current details. Establish presenter matching through the approved
   in-person procedure or an explicitly supported result; keep this separate from
   the source-document signature result.
4. Staff confirms name/address changes and possible existing-Party matches. Collect
   a usable phone separately; any phone OTP confirms possession, not identity.
   Retain current residence separately when it differs from credential address.
5. Save allowed fields and an audit receipt. Display **Identity details verified**
   with method/date and scope, **Staff reviewed**, or **Verification incomplete**.
   Later edits must not inherit verification for changed fields. Customer creation
   can continue through the agreed alternative path when the digital step fails.

## Repository fit and smallest coherent implementation boundary

Read-only inspection confirms `apps/tenant_apps/party/models/document.py` already
holds PartyIdentifier and PartyDocument with verification flags/timestamps. The
identifier form in `apps/tenant_apps/party/forms.py` accepts a generic value and
optional mask; its cleaning trims/uppercases the value. This is not an Aadhaar
verification or data-minimisation service. No Aadhaar/provider connector was found
in the inspected application/settings sources.

Reuse Party, addresses, contacts, existing action checks in `party/access.py`, and
private media. Existing gallery removal preserves file bytes for historical uses;
therefore it is not a suitable unmodified consent-deletion workflow for identity
evidence. Do not automatically add a government-sourced photo to the ordinary
gallery, default borrower photo, loan ticket or portable export: each downstream
use must be within the approved purpose and retention rules.

If delivery is selected, design one small Party-owned verification-attempt/evidence
record with a selected integration and explicit field provenance. Avoid relying
solely on a mutable `is_verified` flag or adding a provider framework. Exact schema,
permissions and retention require an ADR after method selection. The implementation
must preserve these existing architectural boundaries:

- Direct Workspace ownership, forced RLS and same-Workspace parent checks. Resolve
  legal lender identity separately from Workspace: three branches do not establish
  three legal entities, nor does a shared owner establish one eligible registration.
- Server-authenticated, replay-safe callbacks resolve a previously created request;
  never trust a callback-supplied Workspace or Party ID. Signed/expiring browser
  return state is not proof that verification succeeded. Recheck actor access before
  staff accepts fields; repeated delivery must neither duplicate Parties nor billing.
- Keep Aadhaar/PIN/OTP/raw responses out of logs, generic JSON metadata and analytics.
  Process only within approved hosting and storage arrangements. Do not create
  real-identity fixtures or store evidence in the OneDrive checkout.
- Define a field allowlist and retention schedule before collection. Prefer name,
  necessary address, separately obtained contact and a minimal evidence receipt.
  Photo/DOB/last-four/reference retention requires a demonstrated purpose. Do not
  use last-four digits as a unique key or add a full-number hash as a universal ID.
- No cross-Workspace matching or staff access expansion, no retrospective imported
  verification claims, no automatic loan approvals and no changes to issued tickets.
  Identity status alone does not establish capacity, collateral title or credit risk.
- Resolve withdrawal/deletion and legally required evidence preservation, including
  providers, backups and downstream documents; no blanket promise of instant erasure.

## Ready-to-send eligibility and quote enquiry (not sent)

Rokkad is a shared-schema, Workspace-isolated loan-management SaaS for independent
pawn-lending businesses. The initial use case is borrower-present onboarding:
with consent, validate identity evidence and fill only required name/address fields.
The lender remains responsible for its lending and customer-verification obligations.

Please confirm in writing:

1. Is this use case supported for licensed pawn-lending proprietorships/other legal
   forms, and which entity must contract/register: each legal lender or Rokkad?
   How are multiple branches under the same lender represented?
2. For the specific proposed method, can Rokkad host the interface, receive the
   callback and process/store allowed fields for the registered lender? Explain the
   permitted arrangement given UIDAI's restriction on verification for another entity.
3. Identify the exact service and authority: OVSE/app credential sharing, offline
   QR/XML, DigiLocker issued-document retrieval, or KUA/Sub-KUA e-KYC. Which current
   registrations/approvals are required? Does the 2026 LITE framework apply?
4. What evidence is returned for source authenticity, credential date and presenter
   presence? Can we request only necessary fields and avoid receiving full Aadhaar
   numbers? How are user-uploaded documents distinguished from issuer documents?
5. What are the data-hosting locations, subprocessors, retention/deletion terms,
   customer consent/withdrawal obligations, evidence-access and incident procedures?
6. Provide the complete pricing at the three volumes above, sandbox/test identities,
   onboarding documents/timeline, callback security and failure/retry semantics.

UIDAI's OVSE page publishes `ovse.registration@uidai.net.in` for clarification.
Confirm the address on the official page before sending. This review prepared the
questions; sending an enquiry or submitting business documents is a separate action.
Before an enquiry, identify Rokkad's contracting legal entity and the lenders' legal
entities/registration types. Existing workspace labels and licence numbers alone
do not answer those questions.

## Delivery gates and pilot acceptance

1. **Eligibility:** written arrangement, registrations, data-flow responsibilities,
   applicable lender obligations and retention accepted. Product owner chooses one
   method and reviews the full quote. No live collection while this is unresolved.
2. **Design:** mock up the five-step journey, consent and alternative route; write
   the specific ADR and staff guide. Keep the public promise prospective.
3. **Build/test:** provider test identities only; cover wrong Workspace, revoked staff
   access, forged/expired/replayed callbacks, mismatched presenter, corrupt evidence,
   repeated submissions, edited verified fields, storage/log leakage and deletion.
4. **Bounded pilot:** one eligible lender/branch, consented users, real credentials
   only after the preceding gates. Measure completion/drop-off, median/p95 time,
   correction rate, fallback use and cost per completed verification. Define numeric
   acceptance thresholds with the lender before pilot launch.
5. **Release:** validate permitted reuse and refresh rules, staff training and source-
   accurate badges. Market only the exact completed capability; do not claim all
   borrowers are verified, fraud-proof lending, or universal KYC compliance.

**Deferred resumption point:** resolve contracting legal entities, then obtain
written eligibility/hosting clarification and quotes. The desk review is complete;
provider selection and implementation remain shelved pending explicit owner resumption.
