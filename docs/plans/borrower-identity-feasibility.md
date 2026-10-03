---
status: active
owner: project
updated: 2026-09-30
tags: [plans, party, identity, feasibility]
related: [future-work.md, ../domain/party.md, ../architecture/control-plane-contracts.md]
---

# Borrower identity verification: feasibility review

## Outcome and scope

**Resumed by the owner on 2026-09-30 for provider comparison and enquiries.**
The owner accepted optional staff guidance for the pilot, with identity evidence
and name/address prefilling, a staff-review alternative and separately optional
phone-possession verification. This introduces no loan-approval gate. The proposed
pilot lender is **J Champalal Pawn Brokers (JCL)**; provider replies should go to
**support@rokkad.com**. Its legal structure remains unconfirmed. Rokkad is operated
by Rajesh Rathod; do not describe it as an incorporated company.
Compare Digio, Surepass and Cashfree before selecting a method/provider. Registration,
paid commitments, implementation and live identity collection are not yet selected.

Desk review completed on 2026-09-26 for FW-009. The owner approved investigation
and the potential promise, **"Verify customer identity and reduce manual entry."**
Technical integration is plausible; eligibility for Rokkad's multi-lender business
model and an all-in commercial quote remain unconfirmed. This is a proposed path,
not an accepted implementation architecture or a claim of regulatory KYC compliance.
No provider accounts, applications, paid services, real identity tests or external
communications were initiated. Production and customer data were not accessed.

**Original 26 September recommendation:** investigate a registered-lender Aadhaar app credential-sharing
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
| Aadhaar app selective credential sharing | Borrower uses the official app to consent/share; staff reviews returned fields and presenter evidence. First-time app setup adds effort. | Eligible verifier registration, permitted hosting and an agreed field/retention contract. | Original preferred enquiry; now compare Surepass's advertised OVSE integration alongside hosted DigiLocker. |
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
| Surepass | Advertises Aadhaar OVSE app/QR workflows, QR/XML verification, DigiLocker links/SDK and sandbox testing. | Exact supported method, lender registration and permitted SaaS role, authenticated callback contract, minimal fields, retention/deletion and all-in price. |
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

Owner-selected pilot policy (30 September): optional guidance, no new mandatory
verification condition for creating/approving a loan. Digital failure or refusal
keeps the staff-review alternative available. Phone possession, source identity,
presenter matching and current residence retain separate evidence and labels.

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

## Provider comparison refreshed 2026-09-30

This is a desk comparison of provider-published capabilities, not measured quality,
confirmed pawn-lender eligibility or a supplier selection. Digio was the first
evaluation candidate in discussion; Surepass is now a co-leading candidate because
its advertised app/OVSE route also matches the original selective-sharing proposal.
Cashfree remains the hosted DigiLocker comparison. Direct UIDAI registration remains
an alternative, not an additional integration to build in the pilot.

| Criterion | Digio | Surepass | Cashfree Secure ID |
| --- | --- | --- | --- |
| Relevant published routes | Aadhaar Offline KYC and DigiLocker integration guides | Aadhaar app/OVSE, QR/XML, DigiLocker API and SDK | DigiLocker hosted consent/document retrieval; Dev Studio also lists Aadhaar OKYC |
| Counter journey to evaluate | Provider-led DigiLocker or offline KYC flow | Aadhaar app scans a request QR and consents, or DigiLocker link/SDK | Create DigiLocker URL, customer completes consent, retrieve issued document details |
| Specific question | Can the standard Aadhaar/PAN template be reduced to necessary identity/address fields? | What registration is required per legal lender, and what exactly differs between its app QR and document QR/XML products? | Can Secure ID be contracted independently of payment services for this multi-lender SaaS use case? |
| Engineering evidence still needed | Current payload, callback authentication, retry/idempotency and deletion contract | Same, plus explicit issuer-document provenance and browser/device support | Same, plus exact permitted Aadhaar service for the selected lender |
| Phone/current residence | Separate possession/residence checks needed | Same; hashed contact evidence or data lookup is not current phone possession | Same; DigiLocker authentication does not verify an arbitrary contact saved in Party |
| Comparable all-in pricing | Not established; written quote required | Not established; written quote required | Not established; written quote required |

Sources checked 30 September:

- [Digio offline KYC](https://documentation.digio.in/digikyc/aadhaar_offline/)
  and [integration](https://documentation.digio.in/digikyc/aadhaar_offline/integration_guide/).
  The web reader returned an empty rendered body for these documentation pages;
  search-index excerpts support the route names, not a fully reviewed API contract.
- [Digio DigiLocker integration](https://documentation.digio.in/digikyc/digilocker/integration_guide/).
- [Surepass Aadhaar verification](https://surepass.io/aadhaar-verification-api/),
  [OVSE workflow](https://surepass.io/aadhaar-ovse-api/),
  [DigiLocker](https://surepass.io/digilocker-api/) and
  [DigiBoost](https://surepass.io/digiboost-sdk/). Its app/OVSE page describes
  consent and face authentication in the Aadhaar app. Product availability for
  JCL/Rokkad remains a written eligibility question. Voice/language support is
  advertised; Tamil and the actual counter-device journey still need demonstration.
- [Cashfree DigiLocker](https://www.cashfree.com/digilocker-api/) and
  [Secure ID Dev Studio](https://www.cashfree.com/devstudio/secureid).
- [UIDAI OVSE](https://uidai.gov.in/hi/ovse) still expressly disallows verification
  on behalf of another entity; provider use is not evidence that our SaaS arrangement
  is permitted.

Do not rank vendor latency, accuracy or compliance slogans as measured results.
Surepass's rental-tenant package prices, Cashfree payment-gateway rates and Digio
Account Aggregator pricing are different products, not prices for this pilot.
Request the same 100/1,000/10,000 monthly completed-check scenarios from all three;
these are quotation scenarios, not claimed actual volumes or commitments.

Provider choice should first pass written eligibility, minimal-data/retention and
technical-security checks, then compare customer completion, staff effort and
total cost. A quoted unit rate alone cannot select the supplier.

## Eligibility and quote enquiry

Prepared for separate enquiries to Digio, Surepass and Cashfree. Replies:
support@rokkad.com. Delivery status is recorded below; do not infer sending from
the prepared text. No borrower data or business identity documents are attached.

**Subject:** Rokkad / J Champalal Pawn Brokers - identity verification eligibility and quote

Hello,

Please route this enquiry to your identity-verification sales/solutions team.
I am Rajesh Rathod, operator of Rokkad (https://rokkad.com), a loan-management SaaS
for independent pawn-lending businesses. Our proposed first pilot lender is
J Champalal Pawn Brokers (JCL). We seek a consent-based, in-branch identity check
and name/address prefilling, initially optional staff guidance with a manual
alternative. Please advise which legal-entity documents you require; this enquiry
does not represent Rokkad as an incorporated company or JCL as an NBFC.

Please confirm:

1. Can you support independent pawn lenders using our multi-tenant SaaS? Who must
   contract/register: Rokkad, each legal lender, or both? How are branches handled,
   and may Rokkad receive/process results for the lender under your arrangement?
2. Which exact service do you recommend: Aadhaar app/OVSE, signed QR/XML OKYC, or
   DigiLocker issued-document retrieval? State required approvals and the permitted
   data flow; we do not assume that one platform registration covers all lenders.
3. Can we request only necessary identity/address fields, without mandatory PAN
   or full Aadhaar-number retention? Explain issuer authenticity, presenter evidence,
   field freshness, consent receipts and optional separately priced phone OTP.
4. Please share API/hosted-flow documentation, synthetic sandbox identities,
   callback authentication/replay protection, result retrieval and retry semantics.
   Can customers complete the flow privately on their phone, with Tamil guidance?
5. Confirm hosting locations, subprocessors, retention/deletion (including backups),
   permitted evidence reuse for repeat customers, and lender-specific data separation.
6. Quote 100, 1,000 and 10,000 completed verifications/month as comparison scenarios,
   not commitments. Include setup/per-lender fees, minimums, prepaid-credit expiry,
   success/failure/retry/abandonment charges, SMS, optional add-ons, taxes and support.
   Include onboarding requirements/timeline and a sample commercial agreement.

Please reply in writing to support@rokkad.com. This is an eligibility/pricing enquiry,
not an order, account-registration request or commitment to a paid plan.

Thank you,
Rajesh Rathod
Rokkad

### Enquiry delivery record

On 30 September, automatic approval review initially rejected sending the prepared
Surepass message. The owner subsequently explicitly approved the exact enquiry to
all three named recipients from admin@rokkad.com. All three were sent separately,
with the body above and provider-specific subject prefixes. Gmail confirmed each
send, and the final Sent search showed exactly three matching conversations:

| Provider | Recipient | Sent time, 30 September 2026 (IST) |
| --- | --- | --- |
| Surepass | contact@surepass.io | 15:15 |
| Digio | support@digio.in | 15:16 |
| Cashfree | care@cashfree.com | 15:17 |

Each body requests replies to support@rokkad.com; the sender is admin@rokkad.com.
This is a written reply-address request, not a changed mail-account Reply-To setting.
Sent evidence is saved in `outputs/fw009/provider-enquiries-sent.png`.
Gmail sending is confirmed. Digio's acknowledgement/business-team routing is
confirmed below; other provider delivery and substantive eligibility/pricing answers
are not established by this checkpoint. Do not resend automatically.

Verified public routing contacts: Surepass contact@surepass.io on its
[contact page](https://surepass.io/contact-us/); Digio support@digio.in on its
[official site](https://www.digio.in/); Cashfree care@cashfree.com on its
[pricing contact page](https://www.cashfree.com/payment-gateway-charges/).
The latter two are general routing addresses, not confirmed dedicated identity-sales
inboxes. Each message asks for routing to identity-verification sales/solutions.
Do not use surepass.com, an unrelated service, for Surepass Technologies enquiries.
JCL's legal structure is not assumed and is unnecessary to request the provider's
initial eligibility/document requirements. Substantive provider answers remain pending.

### Digio acknowledgement reviewed 30 September

Richa Sharma of Digio Support Desk replied at **16:44 IST** from support@digio.in:
"Looping in Business Team to connect with you." The message copies
**Digio Business Team <bd@digio.in>**, is addressed to admin@rokkad.com, and also
copies support@digio.in. Gmail shows signing by digio.in and mailing through
digiosupport.zohodesk.in. The requested support@rokkad.com reply address was not
included among this response's recipients.

This establishes receipt and a handoff to the business team, not confirmation of
lender/platform eligibility, permitted data handling, method availability or price.
No quote, document request or substantive answer to the six questions was supplied.
Await the business team's response; do not start registration/integration on this
acknowledgement. Review only; no follow-up message was sent.

## Original detailed enquiry checklist (26 September)

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

**Current next step:** obtain written eligibility/hosting clarification and comparable
quotes for the JCL pilot from Digio, Surepass and Cashfree. Resolve legal structures
and required registrations before onboarding. Provider selection, implementation
and live identity collection remain pending; optional guidance is agreed.
