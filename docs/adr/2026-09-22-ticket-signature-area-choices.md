---
status: accepted
owner: loans
updated: 2026-09-22
tags: [adr, loans, documents, signatures]
related:
  - 2026-09-22-ticket-template-authoring-experiment.md
---

# Per-copy signature areas in precision ticket layouts

The owner approved a simple choice: signature areas may already exist in artwork
or preprinted paper, or the client may place editable frames in reserved space.
Do not require duplicate printed boxes. Both borrower and pawnbroker/agent signing
areas remain expected on each copy; this is space for handwriting, not electronic
signature capture or legal certification.

For v4 only, retain per-copy `signature_areas` in the existing versioned layout.
No declaration means editable signature frames, preserving existing layout hashes.
`BACKGROUND` records the selected asset key and SHA-256; `PREPRINTED` records the
same evidence when a guide is selected, otherwise empty asset evidence. The setup
user confirms both roles. Existing draft audit entries retain actor/time and the
resulting definition hash; publication freezes the definition through existing
services. No additional model, approval process or document renderer is introduced.

Draft background changes may leave a stale confirmation so clients can finish
editing. The editor explains that review is needed; publication and rendering
reject changed selected assets/hashes until reconfirmed. Stock checks reject
background-supplied signatures when a profile suppresses backgrounds, and reject
preprinted signatures on a plain-paper profile. A physical stock change without
a changed guide cannot be detected automatically; the client must review its
signature areas again. Packs/clones preserve unchanged artwork evidence; imported
assets remain workspace-local. This records a client assertion, not machine
recognition of signature boxes.

Selecting frames removes the declaration and supplies separate draggable borrower
and pawnbroker frames if none remain. Selecting existing areas removes signature
frames from that copy, retaining the other copy's frames. Client positioning and
PDF review still decide the final placement.

The owner also explicitly deferred printed interest on JCL. A v4-only boolean
`require_interest_rate` defaults to true; explicit false allows omission without
relaxing the complete source payload or altering approved economics. It does not
erase an existing rate frame: clients remove that frame if present. Older schema
contracts and old canonical hashes remain unchanged. Exact-artifact reprints do
not reevaluate these choices.
