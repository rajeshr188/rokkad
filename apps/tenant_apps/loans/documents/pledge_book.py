"""Selectable A4 Form E working previews; render evidence without ORM reads."""
import io
from pathlib import Path
from xml.sax.saxutils import escape

import fitz

from .display import display_date

VERSION = 'form-e-batch-v3'
PAPER = fitz.paper_rect('a4')
LEFT = [('number', 'Pledge no.', 40), ('identity', 'Name and full address of pawner', 180),
        ('date', 'Loan date', 65), ('principal', 'Principal (Rs)', 72),
        ('rates', 'Interest charged', 105), ('tenure', 'Agreed redemption period', 83)]
RIGHT = [('number', 'Pledge no.', 40), ('descriptions', 'Articles, quantity and weight', 150),
         ('valuations', 'Article values (Rs)', 68), ('payments', 'Every payment and date', 112),
         ('closures', 'Redemption / auction date', 58), ('owner', 'Other owner: name / address', 58),
         ('recipients', 'Redeemer / buyer: name / address', 59)]
LANDSCAPE = [('number', 'Pledge no.', 40), ('identity', 'Name and full address of pawner', 108),
             ('date', 'Loan date', 52), ('principal', 'Principal (Rs)', 55),
             ('rates', 'Interest charged', 53), ('tenure', 'Agreed redemption period', 49),
             ('descriptions', 'Articles, quantity and weight', 118), ('valuations', 'Article values (Rs)', 48),
             ('payments', 'Every payment and date', 88), ('closures', 'Redemption / auction date', 52),
             ('owner', 'Other owner: name / address', 58), ('recipients', 'Redeemer / buyer: name / address', 73)]
LAYOUT_CHOICES = [('facing_a4', 'Two facing A4 pages (portrait)'),
                  ('landscape_a4', 'Single A4 sheet (landscape)')]
LAYOUTS = {
    'facing_a4': dict(paper=PAPER, sides=(('Left', LEFT), ('Right', RIGHT)),
                     margin=30, header=91, top=143, bottom=778, min_row=120, size=8,
                     instruction='Print A4 portrait at 100%, single-sided; file each Left / Right pair facing.'),
    'landscape_a4': dict(paper=fitz.paper_rect('a4-l'), sides=(('Landscape', LANDSCAPE),),
                        margin=24, header=119, top=166, bottom=546, min_row=76, size=7.8,
                        instruction='Print A4 landscape at 100%, single-sided; one sheet contains all columns.'),
}


def _story(text, size=8):
    fonts = Path(__file__).resolve().parents[4] / 'static/fonts'
    css = f"""@font-face {{font-family: register; src: url(NotoSansTamil-Regular.ttf);}}
        body {{margin:0; font-family: register, sans-serif; font-size: {size}pt; line-height: 1.2;}}
        p {{margin:0;}}"""
    return fitz.Story(html='<p>' + escape(str(text)).replace('\n', '<br/>') + '</p>', user_css=css, archive=fitz.Archive(str(fonts)))


def _height(text, width, size=8):
    story = _story(text, size)
    more, filled = story.place(fitz.Rect(0, 0, width - 8, 20000))
    if more:
        raise ValueError('A pledge-book field is too long for this preview. Review the source before printing.')
    return fitz.Rect(filled).y1 + 12


def paginate_entries(entries, layout):
    """Shared measurement for readiness and output; one group is a sheet/pair."""
    if layout not in LAYOUTS:
        raise ValueError('Select a supported pledge-book print layout.')
    config = LAYOUTS[layout]
    sides = config['sides']
    top, bottom = config['top'], config['bottom']
    min_row, size = config['min_row'], config['size']
    all_columns = [column for _, columns in sides for column in columns]
    rows = []
    for original in entries:
        row = dict(original, identity=original['borrower'] + '\n' + original['address'], date=display_date(original['date']))
        height = max(min_row, *(_height(row[key], width, size) for key, _, width in all_columns))
        rows.append((row, height))
    if not rows:
        rows = [({'number': 'No entries', **{key: '' for key, _, _ in all_columns if key != 'number'}}, min_row)]
    groups, group, used = [], [], 0
    for row, height in rows:
        if height > bottom - top:
            if group:
                groups.append(group); group, used = [], 0
            # Story continuation state is retained for each column across paired sheets.
            groups.append([(row, height)])
        else:
            if group and used + height > bottom - top:
                groups.append(group); group, used = [], 0
            group.append((row, height)); used += height
    if group:
        groups.append(group)
    return groups


def render_pledge_book(report, layout='facing_a4', *, issuance=None, with_manifest=False):
    """Preserved output uses fixed physical sheet numbers; notes are unnumbered."""
    groups = paginate_entries(report.entries, layout)
    config = LAYOUTS[layout]
    paper, sides = config['paper'], config['sides']
    margin, top, bottom, size = config['margin'], config['top'], config['bottom'], config['size']
    right = margin + sum(column[2] for column in sides[0][1])
    buffer = io.BytesIO()
    writer = fitz.DocumentWriter(buffer)
    metadata, manifest = [], {}
    spread = 0
    for group in groups:
        long_row = len(group) == 1 and group[0][1] > bottom - top
        remaining_stories = None
        part = 0
        while True:
            spread += 1; part += 1
            unfinished = False
            for side, columns in sides:
                device = writer.begin_page(paper)
                y, boundaries = top, [top]
                for ri, (row, height) in enumerate(group):
                    if 'loan_id' in row:
                        page_number = (issuance['first_page'] if issuance else 1) + len(metadata)
                        manifest.setdefault(row['loan_id'], [page_number, page_number])[1] = page_number
                    height = min(height, bottom - top)
                    x = margin
                    for ci, (key, _, width) in enumerate(columns):
                        token = (side, ri, ci)
                        if long_row:
                            if remaining_stories is None:
                                remaining_stories = {}
                            if part == 1 or key == 'number':
                                remaining_stories[token] = _story(row[key] + ('\n(cont.)' if part > 1 else ''), size)
                            story = remaining_stories.get(token)
                        else:
                            story = _story(row[key], size)
                        if story is not None:
                            more, _ = story.place(fitz.Rect(x + 4, y + 5, x + width - 4, y + height - 5))
                            story.draw(device)
                            unfinished = unfinished or bool(more)
                            if long_row and not more:
                                remaining_stories[token] = None
                            if more and not long_row:
                                raise ValueError('A pledge-book row failed its measured fit; no clipped PDF was produced.')
                        x += width
                    y += height; boundaries.append(y)
                # Close unused space visibly. A preview never assigns a permanent page.
                if bottom - y >= 30:
                    story = _story('Unused space closed - do not add new pledges here.', 8)
                    story.place(fitz.Rect(margin + 10, y + 10, right - 10, bottom - 5)); story.draw(device)
                writer.end_page()
                metadata.append((side, spread, part, columns, boundaries))
            if not unfinished:
                break
            if part > 50:
                writer.close()
                raise ValueError('Pledge entry exceeds the supported continuation size.')
    writer.close()
    with fitz.open(stream=buffer.getvalue(), filetype='pdf') as doc:
        for page, (side, spread, part, columns, boundaries) in zip(doc, metadata):
            page.insert_text((margin, 27), 'FORM E - PLEDGE BOOK | ' + ('PRESERVED PRINT BATCH' if issuance else 'WORKING PREVIEW'), fontsize=12)
            unit = 'Pair' if layout == 'facing_a4' else 'Page'
            reference = f"Book {issuance['reference']} | Page {issuance['first_page'] + page.number} - {side}" if issuance else f'{unit} {spread} - {side}'
            page.insert_text((margin, 42), 'Section 10(1)(a) and Rule 7 | ' + reference + (' - continuation' if part > 1 else ''), fontsize=9)
            # Use Story for Unicode scope headings as well as row contents.
            scope = f"Licence {report.license.license_number} | Series {report.series.pawn_display_name if report.series else 'All series'}\nLoans {display_date(report.start)} to {display_date(report.end)}; activity through {display_date(report.cutoff)}"
            _overlay(page, scope, fitz.Rect(margin, 47, right, 87), size=8)
            if layout == 'landscape_a4':
                page.insert_text((margin, 103), 'All columns on one sheet. Longer entries may need additional sheets; keep the evidence notes with this document.', fontsize=8)
            x = margin
            for key, label, width in columns:
                page.draw_rect(fitz.Rect(x, config['header'], x + width, top), color=(0.3, 0.3, 0.3), fill=(0.93, 0.94, 0.95), width=0.5)
                _overlay(page, label, fitz.Rect(x + 3, config['header'] + 4, x + width - 3, top - 4), size=min(size, 7.6) if layout == 'landscape_a4' else size)
                for a, b in zip(boundaries, boundaries[1:]):
                    page.draw_rect(fitz.Rect(x, a, x + width, b), color=(0.4, 0.4, 0.4), width=0.4)
                x += width
            if bottom - boundaries[-1] >= 30:
                page.draw_rect(fitz.Rect(margin, boundaries[-1], right, bottom), color=(0.4, 0.4, 0.4), width=0.4)
            footer = 'Preserved reviewed particulars; any unresolved gaps remain in the evidence notes. Generation does not prove filing.' if issuance else 'Read the evidence notes. Not a finalised statutory book page; no permanent page number assigned.'
            page.insert_text((margin, bottom + 15), footer, fontsize=7)
            page.insert_text((margin, bottom + 29), config['instruction'] + ' Later handwriting is not in this PDF.', fontsize=7)
            metadata_y = bottom + 43 if layout == 'facing_a4' else 88
            page.insert_text((margin, metadata_y), VERSION + ' | ' + layout + ' | Generated ' + display_date(report.generated_at) + f' | Sheet {page.number + 1}', fontsize=7)
        notes = [f"Form E - evidence review\nLicence {report.license.license_number}; {len(report.entries)} operational entries.",
                 f"{report.archive_count} archived closed-loan source records in this Workspace are excluded: licence/series mapping is not established. {report.excluded_count} other loans in the selected range have no eligible payout evidence.",
                 'Particulars use records available at generation time, including late entries through the selected business-date cutoff. Blank later-event cells mean no such event is shown in the available evidence, not proof that none occurred. Handwritten later updates are not part of these bytes.']
        if issuance:
            notes.append(f"Book {issuance['reference']} - {issuance['title']}\nGenerated by {issuance['actor']} at {display_date(report.generated_at)} (local time). Layout {layout}; {VERSION}.\nPermanent physical pages {issuance['first_page']} to {issuance['first_page'] + len(metadata) - 1}. Evidence appendix pages are not book pages.\nOpening scope: {issuance['opening_note']}")
        for row in report.entries:
            notes.append(row['number'] + ' | ' + row['source'] + '\n' + '\n'.join(row['warnings']))
        note_pdf = _flow_pdf('\n\n'.join(notes), paper)
        with fitz.open(stream=note_pdf, filetype='pdf') as appendix:
            doc.insert_pdf(appendix)
        pdf = doc.tobytes(garbage=4, deflate=True)
        return (pdf, manifest, len(metadata)) if with_manifest else pdf


def _overlay(page, text, rect, size=8):
    data = io.BytesIO()
    writer = fitz.DocumentWriter(data)
    device = writer.begin_page(page.rect)
    story = _story(text, size)
    more, _ = story.place(rect)
    if more:
        writer.close()
        raise ValueError('Print heading exceeds its available space.')
    story.draw(device); writer.end_page(); writer.close()
    with fitz.open(stream=data.getvalue(), filetype='pdf') as layer:
        page.show_pdf_page(page.rect, layer, 0)


def _flow_pdf(text, paper=PAPER):
    data = io.BytesIO(); writer = fitz.DocumentWriter(data); story = _story(text, 9)
    more, count = True, 0
    while more:
        device = writer.begin_page(paper)
        more, _ = story.place(fitz.Rect(35, 35, paper.width - 35, paper.height - 52)); story.draw(device)
        writer.end_page(); count += 1
        if count > 100:
            writer.close()
            raise ValueError('Evidence notes exceed the supported preview size.')
    writer.close()
    return data.getvalue()
