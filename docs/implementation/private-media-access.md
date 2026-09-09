---
status: active
owner: project
updated: 2026-09-09
tags: [security, media, workspace]
---

# Private business media

RLS isolates database rows. File storage and HTTP delivery are separate boundaries.
This review covers the development application; no production deployment is in use
and no external bucket, CDN or reverse proxy has been verified or changed.

## Inventory and delivery

| Files / storage prefix | Application delivery | Required access |
| --- | --- | --- |
| Borrower photos, `party_profile_photos/` | Workspace Party photo route | Current membership and `contact.view` OR `data.view`; matching Workspace |
| Borrower documents/KYC, `party_documents/` | Workspace Party document download | Same Party view policy; document must match Workspace and borrower |
| Collateral photos, `loans/collateral/` | Existing loan/item/photo route | Loans `data.view`; matching loan/item/photo |
| License evidence, `loans/regulatory/` | Existing license revision download | Workspace settings administration; matching license/revision |
| Layout assets/backgrounds, `loans/documents/` | Existing layout preview/background routes | Workspace settings administration; matching revision |
| Stored issued PDFs, `loans/documents/` | Existing source-document routes; setup issue download | Source view access, or settings administration for setup issue routes |
| Notification attachments, `notify_v2/artifacts/` | Existing artifact download / batch ZIP | Notify view; bulk ZIP additionally requires export |
| Imports and report exports | Request processing / generated response | Existing import/export action checks; no public persisted download directory |
| Company logos, `company_logos/` | Public branding media | Public by current design |
| Account avatars, `profile_pictures/` | Public account presentation media | Existing public presentation behavior retained; these are not borrower photos |

The development media handler now allows only the two presentation prefixes above.
All business and unknown storage prefixes return 404, including normalized traversal
and backslash variants. This also protects existing files without moving them or
changing database file names. A guessed raw URL cannot bypass an authorized view.

Party list/detail and loan borrower thumbnails use explicit Workspace photo URLs.
KYC links use the authorized download route. Party upload widgets retain replacement
and clear controls without emitting storage links. Documents download as attachments;
only ordinary raster photo types render inline, with `nosniff`. Private Party and
reviewed stored-file endpoints set no-store caching directives. File streams are
opened during the authorized request and do not query the database while streaming.

Membership and grants are checked on each new request. This cannot revoke bytes
someone already downloaded. No license-scoped restrictions have been introduced.

## Deployment acceptance still required before production

The application uses local FileSystemStorage today. The optional Cloudflare storage
helper is not the configured default. Its development/production example options
no longer request public-read ACLs and explicitly enable signed URL authentication.
This does not change existing objects or a bucket-level public-serving policy. An application 404 cannot protect a file served
directly by a separate storage origin or reverse proxy.

When choosing the production serving configuration:

1. Keep business objects private. Do not publish a broad `/media/` filesystem alias,
   public bucket or CDN origin covering them. If publishing presentation media,
   expose only the explicit logo/avatar prefixes. Revisit account-avatar visibility
   if the product requires private personal avatars.
2. Let authorized application routes read private objects with server credentials.
   Do not replace these routes with permanent public storage links. If signed URLs
   are introduced later, review their expiry and post-membership-removal behavior.
3. Verify existing borrower, collateral, license, layout and notification object URLs
   against every external origin as an anonymous user; purge previously public cached
   copies if applicable. Verify authorized downloads and denied other-Workspace,
   removed-member and revoked-permission requests through the deployed application.
4. Confirm private responses bypass shared caches. Preserve download content types
   and attachment/nosniff headers. Keep uploaded files outside executable/static code.

MED-01/MED-02 application work and deployment acceptance must be tracked separately
in the [delivery register](../plans/saas-access-media-and-onboarding.md).
