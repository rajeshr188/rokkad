# Counter workflow concept

Open `index.html` in a browser. It runs directly from disk with no server or
external dependencies. Use fictional details only. All changes live in memory;
reset or refresh clears the session. No application records, money, messages,
print jobs are involved.

## Walkthrough

1. Search for Lakshmi and select her, or add a fictional borrower.
2. Continue to collateral. Add/remove an item, edit its details, and optionally
   upload an image or use **Take photo** to capture, review, and retake a camera image. Allow camera access when prompted. If unavailable, upload remains available.
3. Review the illustrative terms and save a sample draft.
4. Confirm review and approve; separately confirm sample cash disbursal.
5. Record a sample repayment, then use the full remaining balance to settle.
6. Confirm the simulated item handoff. Reset to try another journey.

The sidebar previews the shared navigation for Loans, Parties, Rates, Notify,
and Workspace readiness. Rates, Notify, and setup are layout previews, not
implemented management workflows. Workspace switching is explanatory only.

Review the task sequence, information density, terminology, and action placement
before implementing the shared Django shell and first-loan vertical slice.
Production permissions, KYC rules, valuations, financial calculations, official
documents, and lifecycle enforcement must continue to come from existing services.
The fixed example uses same-day repayments with zero interest and fees solely
to demonstrate interaction, not to specify settlement policy.

## Verification

With the optional browser requirements installed, run from the repository root:

```powershell
.\.venv314\Scripts\python.exe docs/ui/prototypes/counter/verify.py
.\.venv314\Scripts\python.exe docs/ui/prototypes/counter/verify_camera.py
```

The script checks the full journey, required confirmations, invalid weight,
borrower search/creation, collateral row changes, local image preview, navigation,
and viewport overflow at 1440×1000 and 390×844. Screenshots go to
`%TEMP%\rokkad-ux-prototype`. This does not replace physical phone/printer checks.

Camera capture stays in browser memory. Closing the camera, capturing, or leaving
the page stops its stream. No audio is requested. Camera browser checks use a
simulated stream; physical device acceptance remains deferred.
