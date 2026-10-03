"""Flow complete khata evidence across A4 pages with the existing Unicode engine."""
from io import BytesIO
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape

import fitz
from reportlab.pdfgen import canvas
from .display import display_money

VERSION = "khata-a4-v1"


def render_document(payload, *, issue_reference):
    def text(value):
        return escape(str(value or "")).replace("\n", "<br/>")

    def paragraph(label, value):
        if label.endswith("(INR)") and value != "Unavailable":
            value = display_money(value, grouping=True)
        return f"<p><b>{text(label)}</b> {text(value)}</p>"

    def money(value):
        return display_money(value, grouping=True)

    terms = payload["agreement"]
    borrower = payload["borrower"]
    parts = [f"<h1>{text(payload['title'])}</h1>",
        paragraph("Khata", payload["account_number"]), paragraph("Series", payload["series"]),
        paragraph("Business date / statement date", payload["as_of"]),
        paragraph("Lender", terms["lender_name"]), paragraph("Lender address", terms["lender_address"]),
        paragraph("Borrower identity recorded at issuance", f"{borrower['name']} ({borrower['code']})"),
        paragraph("Borrower address recorded at issuance", borrower["address"] or "Not recorded"),
        paragraph("Contact", borrower["phone"] or "Not recorded")]
    license = payload["license"]
    if license:
        parts.append(paragraph("Associated licence", license.get("number") or f"Licence ID {license['id']}"))
        parts.append(paragraph("Retained licence revision", license.get("revision_id") or "Not recorded"))
    else:
        parts.append(paragraph("Series association", "Independent khata series; no licence associated"))
    parts += ["<h2>Agreement terms</h2>",
        paragraph("Agreed limit (INR)", terms["agreed_limit"]),
        paragraph("Interest rate", f"{Decimal(terms['monthly_rate']).normalize():f}% per month; {terms['frequency'].lower()} payments in arrears"),
        paragraph("Agreed LTV", f"{(Decimal(terms['ltv']) * 100).normalize():f}% of approved collateral value"),
        paragraph("Agreement revision", terms["number"]),
        paragraph("First withdrawal", payload["opened_on"] or "Not yet made; interest has not started"),
        "<p>Simple interest applies to the full agreed limit from the first withdrawal. "
        "Monthly or annual payment frequency does not change the monthly percentage rate. "
        "The original agreement has a full first-month minimum; later partial months use actual days. "
        "Payments fall on the original monthly or annual anniversary, with short-month clamping. "
        "There is no fixed maturity. Limit/rate amendments split interest from their activation date. "
        "Principal repayment requires formal reduction or settlement and does not restore drawing entitlement.</p>"]
    if payload["source"] and payload["source"]["kind"] == "TERMS_OK":
        parts.append("<p>This amendment is approved for activation. Approval alone does not change live interest or drawing entitlement.</p>")
    if payload.get("correction_notice"):
        parts.append(paragraph("Correction recorded before issuance", f"This source has been corrected by operation {payload['correction_notice']}. This document preserves the original source, not a new receipt or payout."))
    source = payload["source"]
    if source:
        parts += ["<h2>Source transaction</h2>",
            paragraph("Source reference", f"Operation {source['id']} / sequence {source['sequence']}"),
            paragraph("Recorded by", source["actor"])]
        labels = {"WITHDRAW": "Cash paid to borrower", "INTEREST": "Interest received",
            "REVISE": "Principal received with reduction", "SETTLE": "Principal received",
            "CORRECT": "Corrected receipt amount (not a new payment)"}
        if source["kind"] in labels:
            if source["kind"] != "CORRECT" or source["evidence"].get("source_kind") == "INTEREST":
                parts.append(paragraph(labels[source["kind"]] + " (INR)", source["amount"]))
        if source["kind"] == "SETTLE":
            parts.append(paragraph("Interest received through closure (INR)", source["interest_amount"]))
        evidence = source["evidence"]
        for key, label in (("payment_reference", "Payment reference"), ("agreement_reference", "Borrower agreement reference"),
            ("recipient", "Recipient"), ("reference", "Handover reference"), ("received_from", "Received from"),
            ("reason", "Reason"), ("cash_resolution", "Cash correction confirmation"),
            ("resolution_reference", "Correction confirmation reference"),
            ("old_limit", "Previous limit (INR)"), ("new_limit", "Revised limit (INR)"),
            ("old_monthly_rate", "Previous monthly rate (%)"), ("new_monthly_rate", "Revised monthly rate (%)"),
            ("retained_value", "Retained collateral value (INR)"), ("backing", "Retained lending cover at agreed LTV (INR)"),
            ("exchange_policy", "Exchange shortfall policy"), ("overdue_policy", "Overdue interest policy")):
            if key in evidence:
                parts.append(paragraph(label, evidence[key]))
        for warning in evidence.get("warnings", []):
            parts.append(paragraph("Warning accepted", warning))
        for metal, shortfall in evidence.get("shortfalls", {}).items():
            parts.append(paragraph(f"{metal} replacement-value shortfall (INR)", shortfall))
        for valuation in evidence.get("valuations", []):
            rate = valuation["rate_evidence"]
            parts.append(paragraph(f"Approved valuation / item {valuation['item_id']}",
                f"INR {money(valuation['value'])}; {rate['metal']} {rate['purity']}; "
                f"INR {money(rate['buying_rate'])} per gram; effective {rate['effective_at']}; quote {valuation['rate_id']}"))
        if source["parent_id"]:
            parts.append(paragraph("Return authorized by operation", source["parent_id"]))
        if source["correction_of_id"]:
            parts.append(paragraph("Original operation corrected", source["correction_of_id"]))
        for allocation in payload.get("allocations", []):
            parts.append(paragraph("Interest allocation", f"{allocation['start_on']} to {allocation['end_on']} (end excluded); due {allocation['due_on']}; INR {money(allocation['amount'])}"))
        parts += [paragraph("Actual principal after this source (INR)", payload["principal"]),
            paragraph("Unused entitlement after this source (INR)", payload["unused"])]
    else:
        parts += ["<h2>Today's position</h2>", paragraph("State", payload["state"])]
        for key, label in (("principal", "Actual principal outstanding"), ("interest", "Accrued unpaid interest"),
            ("due_interest", "Interest due"), ("overdue_interest", "Interest overdue"), ("outstanding", "Principal plus accrued unpaid interest"),
            ("limit", "Agreed limit (not debt)"), ("unused", "Unused entitlement (not debt)")):
            parts.append(paragraph(label + " (INR)", payload["balances"][key]))
        parts.append("<p>This is a dated balance statement, not a settlement quotation. "
            "Accrued interest includes amounts not yet due, and the opening minimum where applicable.</p>")
        cover = payload.get("cover", {})
        parts.append(paragraph("Eligible collateral value at issuance (INR)", cover.get("value") or "Unavailable"))
        parts.append(paragraph("Collateral-based drawing capacity, suggestion only (INR)", cover.get("capacity") if cover.get("capacity") is not None else "Unavailable"))
        if cover.get("undercovered"):
            parts.append("<p>Retained collateral is below the agreed LTV cover.</p>")
        if cover.get("reason"):
            parts.append(paragraph("Cover / lending check", cover["reason"]))
        for rate in cover.get("quotes", []):
            parts.append(paragraph("Price retained at statement issuance", f"{rate['metal']} {rate['purity']}; "
                f"INR {money(rate['buying_rate'])} per gram; effective {rate['effective_at']}; quote {rate['rate_id']}"))
        parts.append("<h2>Interest schedule</h2>")
        for period in payload.get("interest_schedule", []):
            parts.append(paragraph(f"Period {int(period['index']) + 1}",
                f"{period['start_on']} to {period['end_on']} (end excluded); due {period['due_on']}; "
                f"charged INR {money(period['charge'])}, paid INR {money(period['paid'])}, unpaid INR {money(period['outstanding'])}"))
    parts.append("<h2>Collateral custody at the source / statement date</h2>")
    roles = {r["item_id"]: r["role"] for r in payload.get("selected_items", [])}
    for item in payload["collateral"]:
        parts.append(paragraph(f"Item {item['id']} - {item['custody']}", item["description"]))
        parts.append(paragraph("Details", f"{item['metal']}; quantity {item['quantity']}; gross {item['gross_weight']} g; "
            f"net {item['net_weight']} g; purity {item['purity']}%; storage: {item['storage_reference']}"))
        if item["id"] in roles:
            parts.append(paragraph("Exchange / return selection", "Incoming" if roles[item["id"]] == "IN" else "Outgoing"))
    if not payload["collateral"]:
        parts.append("<p>No collateral recorded.</p>")
    if not source:
        parts.append("<h2>Source history</h2><p>Correction rows are compensation, not additional cash receipts.</p>")
        for op in payload["history"]:
            parts.append(paragraph(f"{op['date']} - {op['kind']} / {op['id']}",
                f"Amount INR {money(op['amount'])}; interest component INR {money(op['interest_amount'])}"))
            if op["correction_of_id"]:
                parts.append(paragraph("Corrects operation", op["correction_of_id"]))
    parts += [paragraph("Issued reference", issue_reference), paragraph("Issued at", payload["issued_at"]),
        "<p>Reprints reproduce this preserved document. Later changes and corrections are recorded separately in the account history. "
        "Financial settlement does not confirm physical collateral return; actual handovers are recorded separately.</p>"]
    fonts = Path(__file__).resolve().parents[4] / "static/fonts"
    css = """@font-face {font-family: khata; src: url(NotoSansTamil-Regular.ttf);}
        body {font-family: khata, sans-serif; font-size: 10pt; line-height: 1.35;}
        h1 {font-size: 20pt; color: #24554f;} h2 {font-size: 13pt; color: #24554f;}
        p {margin: 0 0 7pt;}"""
    story = fitz.Story(html="".join(parts), user_css=css, archive=fitz.Archive(str(fonts)))
    buffer = BytesIO()
    writer = fitz.DocumentWriter(buffer)
    paper = fitz.paper_rect("a4")
    frame = fitz.Rect(40, 38, paper.width - 40, paper.height - 46)
    more = True
    pages = 0
    try:
        while more and pages < 100:
            device = writer.begin_page(paper)
            more, _ = story.place(frame)
            story.draw(device)
            writer.end_page()
            pages += 1
    finally:
        writer.close()
    if more:
        raise ValueError("Khata document exceeds 100 pages; no truncated document was issued.")
    doc = fitz.open(stream=buffer.getvalue(), filetype="pdf")
    try:
        # Keep the established shaped Unicode body; ReportLab supplies consistent
        # page furniture without rasterizing any borrower/source text.
        furniture = BytesIO()
        footer = canvas.Canvas(furniture, pagesize=(paper.width, paper.height), invariant=1)
        for number in range(1, len(doc) + 1):
            footer.setFont("Helvetica", 8)
            footer.setFillColorRGB(.32, .38, .37)
            footer.drawString(40, 25, f"Khata {payload['account_number']} | Page {number} of {len(doc)}")
            footer.showPage()
        footer.save()
        with fitz.open(stream=furniture.getvalue(), filetype="pdf") as overlay:
            for number, page in enumerate(doc):
                page.show_pdf_page(paper, overlay, number)
        doc.set_metadata({"title": payload["title"], "subject": payload["account_number"]})
        return doc.tobytes(garbage=4, deflate=True)
    finally:
        doc.close()
