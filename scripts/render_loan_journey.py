"""Render the shared documentation PNG. Run with the project's Pillow install.

No customer data, browser, network or application database is used.
"""
from pathlib import Path
import math
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "static/images/loan-journey.png"
INK, GREEN, MUTED = "#182e2a", "#176750", "#52665f"
image = Image.new("RGB", (1800, 1370), "#f6f8f4")
draw = ImageDraw.Draw(image)


def font(size, bold=False):
    candidates = [
        Path("C:/Windows/Fonts") / ("arialbd.ttf" if bold else "arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu") / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    raise RuntimeError("Install Arial or DejaVu Sans to render the diagram.")


def text(x, y, value, size=24, color=INK, bold=False):
    draw.text((x, y), value, fill=color, font=font(size, bold))


def card(x, y, w, h, title, lines, *, fill="white", accent=GREEN):
    draw.rounded_rectangle((x, y, x+w, y+h), radius=18, fill=fill, outline="#cbd8cd", width=2)
    draw.rounded_rectangle((x+20, y+22, x+26, y+h-22), radius=3, fill=accent)
    text(x+44, y+22, title, 28, accent, True)
    body_size = 23
    while any(draw.textlength(line, font=font(body_size)) > w-66 for line in lines):
        body_size -= 1
        assert body_size >= 19, title
    for i, line in enumerate(lines):
        text(x+44, y+68+i*31, line, body_size, MUTED)


def arrow(points, color=GREEN):
    draw.line(points, fill=color, width=4, joint="curve")
    (x0,y0),(x,y)=points[-2:]
    angle=math.atan2(y-y0,x-x0)
    draw.polygon([(x,y), (x-15*math.cos(angle-.45),y-15*math.sin(angle-.45)),
                  (x-15*math.cos(angle+.45),y-15*math.sin(angle+.45))], fill=color)


text(65, 42, "ROKKAD  /  THE LOAN JOURNEY", 22, GREEN, True)
text(65, 88, "One loan. Three connected stories.", 48, INK, True)
text(65, 154, "The debt, the pledged items and the decisions behind them.", 29, MUTED)
text(65, 213, "NEW LENDING", 20, GREEN, True)
card(65,250,365,183,"01  Prepare",["Licence, series and product", "Policies, prices and print layout"])
card(495,250,365,183,"02  Draft",["Borrower, items and photos", "Amounts, valuation and terms"])
card(925,250,365,183,"03  Approved",["Checks passed; terms frozen", "Print the approved loan ticket"])
card(1355,250,380,183,"04  Active",["Record disbursal and payout", "Debt and custody now tracked"])
for start in (430,860,1290): arrow([(start,340),(start+65,340)])
arrow([(677,433),(677,485)],"#986d32")
card(65,485,795,177,"Before disbursal",["Split selected rows into another draft; keep one row here.","Correct drafts, or return an approved loan to draft with a reason.","Cancel abandoned loans. Keep the numbers and history."],fill="#fff7e9",accent="#886122")
arrow([(1545,433),(1545,705)])
card(925,485,365,177,"New agreement",["Renewal closes the old loan", "and starts a linked successor.", "Retained / returned items tracked."],fill="#ecf5ef")
card(65,705,795,191,"Other ways into the system",["Reviewed opening balances: dedicated payments and full release.","Supported complete histories: reviewed import and reconciliation.","Historical archive: reference evidence, not an active loan."],fill="#edf1f7",accent="#496482")
arrow([(860,800),(925,800)],"#496482")
card(925,705,810,191,"05  Service the active loan",["Collect payments, review dues and finalize applicable interest.","Track custody, storage, photos, reassessments and loan health.","Payment alone does not close the loan or return jewellery."])
arrow([(1107,705),(1107,662)])
arrow([(1290,565),(1320,565),(1320,455),(1545,455),(1545,433)])
arrow([(1330,896),(1330,965)])
card(925,965,810,203,"06  Closed",["Full release: settle the debt and record all collateral returned.","Counter batch: up to 20 loans. Paper closures: up to 50.","Eligible renewal or guarded auction can also close a loan.","Receipts, documents and event history remain available."],fill="#e7f2ea")
card(65,965,795,203,"Corrections preserve the story",["Completed actions are not edited in place: use guarded reversals.","Resolve later dependencies first; reconcile cash and handover.","Draft split is not partial release. Ordinary partial release is absent.","Auction currently requires exact debt settlement."],fill="#fff7e9",accent="#886122")
draw.line((65,1225,1735,1225), fill="#cbd8cd", width=2)
text(65,1250,"Solid arrows show workflow paths, not automatic actions. Every step has state, role and evidence checks.",25,MUTED)
text(65,1295,"Guided Excel / old-paper loan entry is planned (FW-007). Read the guide for import and reversal boundaries.",24,MUTED)
OUT.parent.mkdir(parents=True,exist_ok=True)
image.save(OUT,optimize=True)
print(OUT)
