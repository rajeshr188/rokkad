"""Manual postal service evidence. Digital reminder outcomes are never consulted."""
import hashlib
import io
import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

import fitz
from PIL import Image
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.tenant_apps.loans.forms_statutory import CatalogueForm, FORMS
from apps.tenant_apps.loans.models.statutory import StatutoryAuctionNotice, StatutoryNoticeEvidence
from apps.tenant_apps.loans.documents.display import display_date

K = StatutoryNoticeEvidence.Kind
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024


class StatutoryNoticeError(ValueError):
    pass


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def _json_value(value):
    return value.isoformat() if hasattr(value, 'isoformat') else value


def _authorize(auction_id, actor):
    from .pawn_auctions import _locked_auction, _require_administrator
    auction = _locked_auction(auction_id)
    _require_administrator(actor, auction.workspace)
    return auction


def _active(auction):
    if auction.state not in {'INITIATED', 'IN_PROGRESS'} or auction.loan.state != 'ACTIVE':
        raise StatutoryNoticeError('Notice handling requires an active loan and an open auction. Historical evidence remains available.')


def _validated(form_type, data, attachment=None):
    form = form_type(data, {'attachment': attachment} if attachment else None)
    if not form.is_valid():
        raise ValidationError(form.errors.as_text())
    return form.cleaned_data


def catalogue_snapshot(auction, data):
    loan = auction.loan
    items = list(loan.collateral_items.order_by('pk'))
    if not items:
        raise StatutoryNoticeError('A catalogue requires the pledged articles.')
    return {
        **{key: _json_value(value) for key, value in data.items() if key not in {'request_key', 'reviewed'}},
        'workspace_id': auction.workspace_id, 'auction_id': auction.pk,
        'auction_number': auction.auction_number, 'scheduled_date': auction.scheduled_date.isoformat(),
        'loan_id': loan.pk, 'loan_number': loan.loan_number, 'loan_date': loan.loan_date.isoformat(),
        'license_number': loan.license.license_number, 'series_id': loan.series_id,
        'borrower_name': loan.borrower.display_name,
        'items': [{'id': item.pk, 'description': item.description, 'metal': item.metal,
                   'quantity': item.quantity, 'gross_weight_g': str(item.gross_weight) if item.gross_weight is not None else 'Not recorded',
                   'net_weight_g': str(item.net_weight)} for item in items],
    }


def render_catalogue(snapshot, *, preview=False):
    """Render only frozen particulars; print signature space, never a fabricated signature."""
    def html(text):
        return escape(str(text)).replace('\n', '<br/>')
    rows = [
        ('Pawnbroker', snapshot['business_name']), ('Place of business', snapshot['business_address']),
        ('Licence number', snapshot['license_number']), ('Pledge number', snapshot['loan_number']),
        ('Loan date', display_date(snapshot['loan_date'])), ('Pawner', snapshot['borrower_name']),
        ('Last-known address', snapshot['borrower_address']),
        ('Sale date and time', f"{display_date(snapshot['scheduled_date'])} {snapshot['sale_time']} (India local time)"),
        ('Place of sale', snapshot['sale_place']), ('Auctioneer', snapshot['auctioneer_name']),
        ('Auctioneer approval', snapshot['auctioneer_reference']), ('Auction reference', snapshot['auction_number']),
    ]
    heading = 'PREVIEW - not issued' if preview else 'Particulars reviewed for manual printing and postal service.'
    content = '<h1>Auction catalogue / notice</h1><p>Tamil Nadu Pawnbrokers Rules, 1943 - Rule 12(7)(i)</p>'
    content += '<p>' + html(heading) + '</p>'
    content += ''.join('<p class="particular"><b>' + html(k) + ':</b> ' + html(v) + '</p>' for k, v in rows)
    content += '<h2>Articles proposed for sale</h2>'
    for index, item in enumerate(snapshot['items'], 1):
        content += '<p>' + html(f"{index}. {item['description']} - {item['metal']}; quantity {item['quantity'] if item['quantity'] is not None else 'not recorded'}; gross weight {item['gross_weight_g']} g; net weight {item['net_weight_g']} g.") + '</p>'
    content += '<p class="signature">Auctioneer signature: ____________________<br/>Date: ____________________</p>'
    content += '<p>This document records the proposed sale particulars. Generation does not establish posting, receipt or permission to conduct the sale.</p>'
    fonts = Path(__file__).resolve().parents[4] / 'static/fonts'
    css = """@font-face {font-family: notice; src: url(NotoSansTamil-Regular.ttf);}
        body {font-family: notice, sans-serif; font-size: 10pt; line-height: 1.45;}
        h1 {font-size: 19pt;} h2 {font-size: 13pt;}
        .particular {margin-top: 7pt; margin-bottom: 7pt;} .signature {margin-top: 25pt;}"""
    story = fitz.Story(html=content, user_css=css, archive=fitz.Archive(str(fonts)))
    buffer = io.BytesIO()
    writer = fitz.DocumentWriter(buffer)
    page_rect = fitz.paper_rect('a4')
    more = True
    pages = 0
    while more:
        device = writer.begin_page(page_rect)
        more, filled = story.place(fitz.Rect(36, 36, page_rect.width - 36, page_rect.height - 48))
        story.draw(device)
        writer.end_page()
        pages += 1
        if pages > 100:
            writer.close()
            raise StatutoryNoticeError('Catalogue content exceeds the supported print size.')
    writer.close()
    with fitz.open(stream=buffer.getvalue(), filetype='pdf') as document:
        for index, page in enumerate(document, 1):
            page.insert_text((36, page.rect.height - 22), f"{snapshot['auction_number']} | tn-rule12-catalogue-v1 | Page {index}", fontsize=8)
        return document.tobytes(garbage=4, deflate=True)


@transaction.atomic
def prepare_catalogue(auction_id, *, data, actor, preview=False):
    auction = _authorize(auction_id, actor)
    values = _validated(CatalogueForm, data)
    existing = StatutoryAuctionNotice.objects.filter(auction=auction).first()
    if existing and not preview:
        if existing.request_key == values['request_key']:
            # Compare reviewed inputs rather than today's mutable Party data.
            for key, value in values.items():
                if key not in {'request_key', 'reviewed'} and existing.snapshot.get(key) != _json_value(value):
                    raise StatutoryNoticeError('This request was already used with different catalogue details.')
            return existing
        raise StatutoryNoticeError('This auction already has a preserved notice. Reprint it, or cancel and prepare a new auction for corrections.')
    _active(auction)
    snapshot = catalogue_snapshot(auction, values)
    pdf = render_catalogue(snapshot, preview=preview)
    if preview:
        return pdf
    notice = StatutoryAuctionNotice(workspace=auction.workspace, auction=auction,
        snapshot=snapshot, snapshot_sha256=_digest(snapshot), artifact_sha256=hashlib.sha256(pdf).hexdigest(),
        request_key=values['request_key'], created_by=actor)
    notice.artifact.save('catalogue.pdf', ContentFile(pdf), save=False)
    notice.save()
    return notice


def _attachment(upload):
    if not upload:
        return None, ''
    if upload.size > MAX_ATTACHMENT_BYTES:
        raise StatutoryNoticeError('Evidence must be no larger than 10 MB.')
    raw = upload.read(MAX_ATTACHMENT_BYTES + 1)
    upload.seek(0)
    if not raw or len(raw) > MAX_ATTACHMENT_BYTES:
        raise StatutoryNoticeError('Evidence is empty or exceeds 10 MB.')
    try:
        if raw.startswith(b'%PDF-'):
            with fitz.open(stream=raw, filetype='pdf') as document:
                if document.is_encrypted or not document.page_count:
                    raise ValueError('Unreadable PDF')
            extension = 'pdf'
        else:
            with Image.open(io.BytesIO(raw)) as picture:
                extension = {'JPEG': 'jpg', 'PNG': 'png'}[picture.format]
                picture.verify()
    except Exception as exc:
        raise StatutoryNoticeError('Upload a readable, unencrypted PDF, JPEG or PNG.') from exc
    return ContentFile(raw, name=f'evidence.{extension}'), hashlib.sha256(raw).hexdigest()


def _date(value):
    return date.fromisoformat(value)


def _evidence(notice):
    return {row.kind: row for row in notice.evidence.order_by('pk')}


def _check_step(notice, kind, occurred_on, details, events):
    today = timezone.localdate()
    sale = _date(notice.snapshot['scheduled_date'])
    if occurred_on > today or occurred_on < timezone.localdate(notice.created_at):
        raise StatutoryNoticeError('Event date must be between notice generation and today; do not backdate service of this document.')
    if K.WITHDRAWN in events:
        raise StatutoryNoticeError('This notice has been withdrawn. Cancel this auction and prepare a corrected one.')
    if kind in events and kind != K.REVIEWED:
        raise StatutoryNoticeError('This step is already recorded. Withdraw the notice if the evidence needs correction.')
    if kind == K.WITHDRAWN and occurred_on != today:
        raise StatutoryNoticeError('Withdrawal is a decision recorded today; it cannot be backdated.')
    prerequisites = {K.POSTED: K.PRINTED, K.ACKNOWLEDGED: K.POSTED, K.RETURNED: K.POSTED,
                     K.REFERRED: K.RETURNED, K.OFFICER_RECEIVED: K.REFERRED, K.CERTIFIED: K.OFFICER_RECEIVED}
    required = prerequisites.get(kind)
    if required and required not in events:
        raise StatutoryNoticeError(f'Record {K(required).label} first.')
    if required and occurred_on < events[required].occurred_on:
        raise StatutoryNoticeError('This event cannot predate its preceding handling step.')
    if kind == K.ACKNOWLEDGED:
        if K.RETURNED in events:
            raise StatutoryNoticeError('A returned notice needs the official-service route; an acknowledgement cannot overwrite its return.')
        delivered = _date(details['delivered_on'])
        if not events[K.POSTED].occurred_on <= delivered <= occurred_on:
            raise StatutoryNoticeError('Delivery must fall between posting and receipt of its proof.')
    if kind == K.CERTIFIED:
        received = events[K.OFFICER_RECEIVED].occurred_on
        affixed, certified = _date(details['affixed_on']), _date(details['certified_on'])
        if not received <= affixed <= certified <= occurred_on:
            raise StatutoryNoticeError('Officer receipt, affixture, certificate issue and certificate receipt must be chronological.')
    if kind == K.REVIEWED:
        issues = service_issues(notice, events)
        if issues:
            raise StatutoryNoticeError(' '.join(issues))
        if occurred_on != today:
            raise StatutoryNoticeError('The readiness review is recorded today; it cannot be backdated.')
        first, second, police = (_date(details[key]) for key in ('first_publication_on', 'second_publication_on', 'police_sent_on'))
        if not timezone.localdate(notice.created_at) <= first < second <= today:
            raise StatutoryNoticeError('Record two distinct publication dates after this catalogue was prepared and no later than today.')
        if (sale - second).days < 11:
            raise StatutoryNoticeError('The second newspaper publication must allow ten clear intervening days before sale.')
        if not timezone.localdate(notice.created_at) <= police <= today or (sale - police).days < 7:
            raise StatutoryNoticeError('Police catalogue copies need at least one week before sale and evidence of actual dispatch.')
        if _date(details['permission_expires_on']) < sale:
            raise StatutoryNoticeError('The permission must cover the scheduled auction date.')


def service_issues(notice, events=None):
    events = events if events is not None else _evidence(notice)
    issues = []
    if K.WITHDRAWN in events:
        issues.append('Notice withdrawn: cancel and prepare a corrected auction.')
    if K.PRINTED not in events:
        issues.append('Record actual printing and auctioneer signing.')
    posting = events.get(K.POSTED)
    if not posting:
        issues.append('Record postal dispatch and attach the booking receipt.')
    elif (_date(notice.snapshot['scheduled_date']) - posting.occurred_on).days < 45:
        issues.append('The sale does not allow 45 days after posting.')
    if K.RETURNED in events:
        if K.CERTIFIED not in events:
            issues.append('Returned cover: complete the official referral and certificate route.')
        if K.REFERRED in events and (events[K.REFERRED].occurred_on - events[K.RETURNED].occurred_on).days > 7:
            issues.append('Referral exceeded the seven-day window. Review with the auctioneer and prepare a new auction/notice.')
        if K.CERTIFIED in events and K.OFFICER_RECEIVED in events:
            details = events[K.CERTIFIED].details
            received = events[K.OFFICER_RECEIVED].occurred_on
            if (_date(details['affixed_on']) - received).days > 7:
                issues.append('Official affixture/proclamation exceeded seven days from officer receipt.')
            if (_date(details['certified_on']) - _date(details['affixed_on'])).days > 5:
                issues.append('Official certification exceeded five days from affixture/proclamation.')
    elif K.ACKNOWLEDGED not in events:
        issues.append('Attach acknowledgement / proof of delivery; posting alone is insufficient.')
    return issues


@transaction.atomic
def record_handling(auction_id, *, kind, data, actor, attachment=None):
    auction = _authorize(auction_id, actor)
    try:
        notice = StatutoryAuctionNotice.objects.get(auction=auction)
        form_type = FORMS[kind]
    except (StatutoryAuctionNotice.DoesNotExist, KeyError) as exc:
        raise StatutoryNoticeError('Prepare the catalogue and select a supported handling step.') from exc
    values = _validated(form_type, data, attachment)
    content, sha256 = _attachment(values.pop('attachment', None))
    request_key = values.pop('request_key')
    occurred_on = values.pop('occurred_on')
    details = {key: _json_value(value) for key, value in values.items()}
    existing = notice.evidence.filter(request_key=request_key).first()
    if existing:
        if (existing.kind, existing.occurred_on, existing.details, existing.attachment_sha256) != (kind, occurred_on, details, sha256):
            raise StatutoryNoticeError('This request was already used with different evidence.')
        return existing
    _active(auction)
    _check_step(notice, kind, occurred_on, details, _evidence(notice))
    row = StatutoryNoticeEvidence(workspace=auction.workspace, notice=notice, kind=kind,
        occurred_on=occurred_on, details=details, attachment_sha256=sha256,
        request_key=request_key, created_by=actor)
    if content:
        row.attachment.save(content.name, content, save=False)
    row.save()
    return row


@dataclass(frozen=True)
class AuctionReadiness:
    issues: tuple[str, ...]
    eligible_on: date | None
    notice: object = None

    @property
    def ready(self):
        return not self.issues


def auction_readiness(auction):
    notice = StatutoryAuctionNotice.objects.filter(auction=auction, workspace_id=auction.workspace_id).first()
    if not notice:
        return AuctionReadiness(('Prepare and review the statutory auction catalogue.',), None)
    events = _evidence(notice)
    issues = service_issues(notice, events)
    if auction.state not in {'INITIATED', 'IN_PROGRESS'}:
        issues.append('This auction attempt is no longer open; its evidence is retained for reference.')
    if notice.snapshot['scheduled_date'] != auction.scheduled_date.isoformat():
        issues.append('Auction date differs from the served catalogue. Cancel and prepare a new auction.')
    review = events.get(K.REVIEWED)
    if not review:
        issues.append('An administrator must review service, permission and publication evidence.')
    else:
        if any(row.pk > review.pk and row.kind != K.REVIEWED for row in events.values()):
            issues.append('Handling evidence changed after review; review the current evidence again.')
        if _date(review.details['permission_expires_on']) < timezone.localdate():
            issues.append('The recorded auction permission has expired.')
    eligible = events[K.POSTED].occurred_on + timedelta(days=45) if K.POSTED in events else None
    if timezone.localdate() < auction.scheduled_date:
        issues.append('Wait until the scheduled auction date.')
    elif timezone.localdate() > auction.scheduled_date:
        issues.append('The advertised sale date has passed. Cancel and prepare a newly scheduled auction.')
    if auction.loan.state != 'ACTIVE':
        issues.append('The loan is no longer active.')
    return AuctionReadiness(tuple(issues), eligible, notice)


def require_statutory_readiness(auction):
    from .pawn_auctions import PawnAuctionError
    readiness = auction_readiness(auction)
    if not readiness.ready:
        raise PawnAuctionError('Statutory notice review needs attention: ' + ' '.join(readiness.issues))
    return readiness
