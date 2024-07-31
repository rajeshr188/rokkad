import io
from io import BytesIO
from itertools import groupby

import reportlab.rl_config

reportlab.rl_config.warnOnMissingFontGlyphs = 1

from django.http import HttpResponse
from num2words import num2words
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape, letter, mm
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, inch, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (Flowable, Frame, FrameBreak, Image,
                                KeepTogether, ListFlowable, ListItem,
                                PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)
from reportlab.platypus.doctemplate import PageTemplate

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.girvi.models import Loan

from .tamfont import tamfont

PAGESIZE = (140 * mm, 216 * mm)
BASE_MARGIN = 5 * mm


class CentreLine(Flowable):
    """
    Draws a dotted line in the centre of the page vertically to tear along
    """

    def __init__(self):
        Flowable.__init__(self)

    def draw(self):
        # Set the line width and style
        self.canv.setLineWidth(0.5)
        self.canv.setDash(1, 3)  # 1pt on, 3pt off

        # Calculate the center of the page
        center_x = landscape(A4)[0] / 2
        center_y = landscape(A4)[1] / 2

        # Draw the dotted line from top to bottom at the center of the page
        self.canv.line(center_x, landscape(A4)[1], center_x, 0)


class BoxyLine(Flowable):
    """
    Draw a box + line + text

    -----------------------------------------
    | foobar |
    ---------

    """

    def __init__(self, x=0, y=-15, width=50, height=10, text=""):
        Flowable.__init__(self)
        self.x = x
        self.y = y
        self.text = text

    def draw(self):
        """
        Draw the shape, text, etc
        """
        self.canv.line(self.x, 0, 350, 0)
        self.canv.drawString(self.x + 5, self.y + 3, self.text)


def create_frames(page_width, page_height, margin=10, separation=10):
    """
    Creates left and right frames for a page with specified dimensions.

    Args:
    - page_width: Width of the page.
    - page_height: Height of the page.
    - margin: Margin from the page edges.
    - separation: Space between the left and right frames.

    Returns:
    A tuple containing the left and right Frame objects.
    """
    mm = 1 / 25.4 * 72  # Millimeters to points conversion factor
    frame_width = (page_width - 2 * margin * mm - separation * mm) / 2
    frame_height = page_height - 2 * margin * mm

    left_frame = Frame(
        margin * mm,
        margin * mm,
        width=frame_width,
        height=frame_height,
        showBoundary=1,  # Set to 0 to hide boundary
    )

    right_frame = Frame(
        page_width / 2 + separation * mm / 2,
        margin * mm,
        width=frame_width,
        height=frame_height,
        showBoundary=1,  # Set to 0 to hide boundary
    )

    return left_frame, right_frame


def generate_loan_items_table(loan, styles):
    """
    Generates a table of loan items for a given loan.

    Args:
    - loan: The loan object containing loan items.
    - styles: A dictionary of styles for formatting the table content.

    Returns:
    A Table object populated with loan items data.
    """
    boldStyle = ParagraphStyle(
        "Bold", parent=styles["Normal"], fontName="Helvetica-Bold"
    )
    # Initialize table data with headers
    li_data = [["Item Description", "Weight", "Amount", "Value"]]

    # Populate table data with loan items
    for i, item in enumerate(loan.loanitems.all(), start=1):
        itemdesc = Paragraph(item.itemdesc, styles["Normal"])
        li_data.append(
            [
                f"{i}.{item.itemdesc}-{item.itemtype}",
                item.weight,
                item.loanamount,
                item.current_value(),
            ]
        )

    # Append total row
    li_data.append(
        [
            "Total",
            loan.formatted_weight(joiner=","),
            Paragraph(f"{loan.loan_amount}", boldStyle),
            loan.current_value(),
        ]
    )

    # Append loan amount in words
    li_data.append(
        [
            Paragraph(
                f"Loan Amount In Words: <b><font size=10>{num2words(loan.loan_amount, lang='en_IN').title()} rupees only</font></b>",
                styles["Normal"],
            ),
            "",
            "",
            "",
        ]
    )

    # Create the table
    loanitems_table = Table(li_data)

    # Set table style
    loanitems_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                (
                    "SPAN",
                    (0, -1),
                    (-1, -1),
                ),  # Span the first cell of the last row across all columns
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ]
        )
    )

    return loanitems_table


def draw_center_dotted_line(canvas, page_size=A4, orientation="landscape"):
    """
    Draws a dotted line at the center of the page.

    Args:
    - canvas: The canvas object to draw on.
    - page_size: The size of the page, default is A4.
    - orientation: The orientation of the page, 'portrait' or 'landscape'.
    """
    # Set the line width and style
    canvas.setLineWidth(0.5)
    canvas.setDash(1, 3)  # 1pt on, 3pt off

    # Adjust page size for orientation
    if orientation == "landscape":
        page_width, page_height = landscape(page_size)
    else:
        page_width, page_height = page_size

    # Calculate the center of the page
    center_x = page_width / 2
    center_y = page_height / 2

    # Draw the dotted line from top to bottom at the center of the page
    canvas.line(center_x, page_height, center_x, 0)


def create_loan_header_table(loan, styles, spacer):
    """
    Creates a header table for a loan document.

    Args:
    - loan: The loan object containing loan details.
    - styles: A dictionary of styles for formatting the table content.

    Returns:
    A Table object populated with loan header data.
    """
    logo = Image("static/images/falconx.png", 50, 50)
    shop_license = loan.series.license
    customer = loan.customer
    # Assuming 'logo', 'shop_license', 'customer', and 'spacer' are defined elsewhere and accessible
    header_data = [
        [
            Paragraph("Sec Rules 8", styles["Normal"]),
            Paragraph(
                f"Pawn Ticket <br/> <font name='custom_noto'>{tamfont('அடகு சீட்டு ').tam()}</font>",
                styles["Heading3"],
            ),
            Paragraph(f"{loan.series.license.name}", styles["Normal"]),
        ],
        [
            logo,
            [
                Paragraph(shop_license.shopname, styles["Heading3"]),
                Paragraph(
                    f"<font size=10>{shop_license.address}</font>", styles["Normal"]
                ),
                Paragraph(
                    f"<font size=6>Propreitor :{shop_license.propreitor}</font>",
                    styles["Normal"],
                ),
            ],
            [
                Paragraph(f"LoanID : <b>{loan.loan_id}</b>", styles["Normal"]),
                Paragraph(
                    f"Date: <b>{loan.loan_date.strftime('%d-%m-%Y')}</b>",
                    styles["Normal"],
                ),
            ],
        ],
        [
            BoxyLine(text="Customer"),
        ],
        [spacer],
        [
            logo,
            [
                Paragraph(
                    f"{customer.name} {customer.relatedas} {customer.relatedto}".title(),
                    styles["Heading3"],
                ),
                Paragraph(
                    f"""{loan.customer.address.first()}<br />ph:{loan.customer.contactno.first()}""",
                    styles["Normal"],
                ),
            ],
            "",
        ],
        [BoxyLine(text="Following article/s are pawned with me:")],
        [spacer],
    ]

    header = Table(header_data)
    header_style = TableStyle(
        [
            ("BOX", (0, 0), (-1, -1), 0.25, colors.black),
            ("SPAN", (0, 7), (-1, 7)),
            ("SPAN", (0, 8), (-1, 8)),
            ("SPAN", (0, 11), (-1, 11)),
            ("BOX", (0, 0), (-1, 0), 0.25, colors.black),  # Add border to the first row
            (
                "BOX",
                (0, 1),
                (-1, 1),
                0.25,
                colors.black,
            ),  # Add border to the second row
            ("BOX", (0, 4), (-1, 4), 0.25, colors.black),  # Add border to the fifth row
        ]
    )
    header.setStyle(header_style)
    return header


def get_label(loan, styles):
    """
    Generates a label for the loan document.

    Args:
    - loan: The loan object containing loan details.
    - styles: A dictionary of styles for formatting the label content.

    Returns:
    A Table object populated with label data.
    """

    normal = styles["Normal"]
    normal.fontName = "Helvetica"
    normal.fontSize = 10
    label = Table(
        [
            [
                Paragraph(
                    f"""<b>{loan.loan_id} {loan.loan_date.date()}</b><br/>
                    <b>{loan.loan_amount} {loan.customer.name}</b><br/>
                    <b>{loan.formatted_weight()}</b>""",
                    styles["Normal"],
                ),
                Paragraph(f"<b>Items:</b> {loan.item_desc}", styles["Normal"]),
            ]
        ],
        colWidths=[None, None],
    )
    label_style = TableStyle(
        [
            ("BOX", (0, 0), (-1, -1), 0.25, colors.black),
            ("BOX", (0, 0), (-1, 0), 0.25, colors.black),  # Add border to the first row
            (
                "BOX",
                (0, 1),
                (-1, 1),
                0.25,
                colors.black,
            ),  # Add border to the second row
        ]
    )
    label.setStyle(label_style)
    return label


def create_terms_flowable(styles, simple_tblstyle):
    """
    Creates a flowable for the terms section.

    Args:
    - normal: The style to be applied to the paragraphs.
    - simple_tblstyle: The style to be applied to the table.

    Returns:
    A flowable object containing the terms section.
    """
    normal = styles["Normal"]
    normal.fontName = "Helvetica"
    normal.fontSize = 8
    terms = Table(
        [
            [
                ListFlowable(
                    [
                        Paragraph(
                            "Time agreed for redemption of articles is 3 months.",
                            normal,
                        ),
                        Paragraph("Above mentioned articles are my own", normal),
                        Paragraph("My monthly income is above Rs:", normal),
                        Paragraph(
                            "Working Hours:9:00 am to 1:00 pm & 2:00 pm to 7:00pm Sunday Holiday",
                            normal,
                        ),
                        Paragraph(
                            "The conditions printed overleaf were read over and signed by me after understanding the same.",
                            normal,
                        ),
                    ],
                    bulletType="bullet",
                )
            ],
        ]
    )
    terms.setStyle(simple_tblstyle)

    return terms


def create_signature_flowable(styles, simple_tblstyle):
    """
    Creates a signature table flowable.

    Args:
    - normal: The style object for normal text.
    - simple_tblstyle: The table style to be applied.

    Returns:
    A Table flowable object for signatures.
    """
    normal = styles["Normal"]
    normal.fontName = "Helvetica"
    normal.fontSize = 8

    signature = Table(
        [
            ["", ""],
            [
                Paragraph(
                    "<font size=8>Signature/Thumb Impression of the pawner</font>",
                    normal,
                ),
                Paragraph(
                    "<font size=8>Signature of the Pawn broker/his Agent</font>", normal
                ),
            ],
        ]
    )
    signature.setStyle(simple_tblstyle)

    return signature


def page3(styles):
    """
    Generates the terms and conditions section for the third page of the loan document.

    Args:
    - styles: A dictionary containing styles for formatting the document.
    - tamfont: A function to handle Tamil font rendering.

    Returns:
    A list of flowables to be added to a frame on the third page.
    """
    normal = styles[
        "Normal"
    ]  # Assuming 'Normal' style is defined in the styles dictionary
    centeredHeading2 = ParagraphStyle(
        name="CenteredHeading2",
        parent=styles["Heading2"],
        alignment=TA_CENTER,
    )

    terms_conditions_flowables = [
        Paragraph("Terms & Conditions", centeredHeading2),
        ListFlowable(
            [
                Paragraph(
                    "The rate of interest on any pledged articles shall not exceed 24% per annum.",
                    normal,
                ),
                Paragraph(
                    "Every Pledge shall be redeemable within a period of one year or such longer period as may be provided in the contract between the parties from the day of pawning and shall further continue to be redeemable during seven days of grace following the said period. A pledge shall further continue to be redeemable until it is disposed of as provided in the act although the period of redemption and of grace have expired.",
                    normal,
                ),
                Paragraph(
                    "Rate of Interest charged 12% per annum. The time agreed upon for redemption of the article in months only.",
                    normal,
                ),
                Paragraph(
                    f"<font name='custom_noto'>{tamfont('3 மதத்திற்கு ஒரு முறை  தவறாமல் வட்டி செலுத்தவேண்டும் .').tam()}</font>",
                    normal,
                ),
                Paragraph(
                    f"<font name='custom_noto'>{tamfont('இந்த ரசித்து கொண்டுவந்ததால் தன பொருள் (அ ) நகை கொடுக்கப்படும்').tam()} </font>",
                    normal,
                ),
                Paragraph(
                    f"<font name='custom_noto'>{tamfont('வியாபாரம் நேரம் :காலை  9:00 முதல் பகல் 1:00 மணி வரை ,பகல் 2:00 மணி முதல் மலை 7:00 மணி வரை  ஞாயுறு விடுமுறை .').tam()}</font>",
                    normal,
                ),
                Paragraph(
                    f"<font name='custom_noto'>{tamfont('இந்த ரசித்து பிறர் வசம்  கொடுக்கக்கூடாது').tam()} </font>",
                    normal,
                ),
                Paragraph(
                    f"<font name='custom_noto'>{tamfont('ஒரு வருடம் 7 நாட்களுக்குமேல் தாங்கள் அடகு வாய்த்த பொருட்கள் ஏல்லத்தில் விட படும்').tam()}</font>",
                    normal,
                ),
                Paragraph(
                    f"<font name='custom_noto'>{tamfont('குறிப்பு: மதத்திற்கு அவ்வளவு நாட்கள் குறையினும் முழு மாத வட்டி செலுத்தவேண்டும் .நீங்கள் வரு இடம் போகும் பட்சத்தில் விலாசம் தெரிவிக்க வேண்டும்.').tam()}</font>",
                    normal,
                ),
                Paragraph(
                    f"<font name='custom_noto'>{tamfont('இதில் கண்ட நகைகள் சரிபாத்து பெற்றுக்கொண்டேன் .').tam()}</font>",
                    normal,
                ),
            ],
            bulletType="bullet",
        ),
    ]

    return terms_conditions_flowables


def page4(styles):
    normal = styles[
        "Normal"
    ]  # Assuming 'Normal' style is defined in the styles dictionary
    centeredHeading2 = ParagraphStyle(
        name="CenteredHeading2",
        parent=styles["Heading2"],
        alignment=TA_CENTER,
    )
    d3 = tamfont(
        """<font name='custom_noto'>
        (8(6) பிரிவையும்  6(1) விதியையும் பார்க்கவும் )<br/>
        அடகு சீட்டு தொலைந்து விட்டது அல்லது அழிந்து விட்டது என்று அடகு வைத்தவரால் கொடுக்கப்படும் உறுதிமொழி <br/>

        பெயர் .............................................................................................................................
        தந்தை /கணவர் ..................................................................................................................
        ஊர் ................................................................தாலுகா ......................................................
        நாலிட்ட .............................................................என்னுள்ள (தெரிந்தால் ) அடகு சீட்டை பெற்றுக்கொண்டேன் என்றும் அது இப்போது தொலைந்துவிட்டது /அழிந்துவிட்டது என்றும் எனக்கு நன்றாக தெரிந்திருந்து நான் அவ்வாறு நம்புகின்ற அளவில் இந்த அடகு வாய்த்த சீட்டு என்னால் எவருக்கும் விற்கப்படவில்லை ஒப்படிக்க படவில்லை 
        அல்லது மாற்றப்படவில்லை என்றும் தமிழ்நாடு 1943-ஆம் ஆண்டு அடகுக்கடைக்காரர் சட்டம் (23,1943)8-வது பிரிவை சேர்ந்த (6)உட்பிரிவின்படி உளமாரவும் உண்மையாகவும் உறுதிமொழி கூறுகின்றேன் .<br/>

            மேலே குறிப்பிட்டுள்ள பொருள் /பொருள்கள் பின்வரும் விவரம் :<br/>
        உள்ளதாகும் /உள்ளவையாகும் :<br/><br/>
            அடகு வைத்தவரின் கையொப்பம் :<br/>
            தொழில் :<br/>
            முகவரி:<br/>
            நாள் :<br/><br/>
        மேற்படி உறுதிமொழி கொடுத்தவர் ......................................................<br/>
        என்பவர் எனக்கு தெரியும் என்று ......................சேர்ந்த .......................................நன் என்னும் மேற்படி சட்டத்தின் 8-வது பிரிவை சேர்ந்த (6) உட்பிரிவின்படி உண்மையாகவும் உறுதிமொழி கூறுகின்றேன் <br/><br/>
            அடையாளம் கொடுப்பவரின் கையொப்பம் :<br/>
            தொழில் :<br/>
            முகவரி :<br/>
            நாள் :<br/>
        </font>"""
    )
    d3 = tamfont.tam(d3)

    right_flowables_page2 = [
        Paragraph(
            f"D3 <font name='custom_noto'> {tamfont('படிவம்').tam()}</font>",
            centeredHeading2,
        ),
        Paragraph(f"{d3}", styles["Normal"]),
    ]

    return right_flowables_page2


def get_loan_template(loan):
    pdfmetrics.registerFont(
        TTFont("custom_noto", "static/fonts/custom_noto.ttf"),
    )
    # Create a file-like buffer to receive PDF data.
    buffer = io.BytesIO()
    my_canvas = Canvas(buffer, pagesize=landscape(A4))
    w, h = my_canvas._pagesize
    spacer = Spacer(0, 0.15 * inch)

    # Define styles for the paragraphs
    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    normal.alignment = TA_JUSTIFY

    simple_tblstyle = TableStyle(
        [
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.black),
            ("BOX", (0, 0), (-1, -1), 0.25, colors.black),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]
    )

    header = create_loan_header_table(loan, styles, spacer)
    loanitems_table = generate_loan_items_table(loan, styles)
    terms = create_terms_flowable(styles, simple_tblstyle)
    sign = create_signature_flowable(styles, simple_tblstyle)
    release_para = Table(
        [
            [
                Paragraph(
                    f"""
    Principle Rs. {loan.loan_amount} Interest Rs. ...............Total Rs. ....................I hereby acknowledge to have paid <br/>on .........
    and received the Jewel/Jewels in good condition and this cancels my account.<br/>
    Signature or Thumb Impression of the Pawner:............................................<br />
    """,
                    normal,
                )
            ]
        ]
    )
    release_para.setStyle(simple_tblstyle)

    flowables = [header, loanitems_table, spacer, sign]
    left_flowables = [*flowables, terms]
    right_flowables = [*flowables, release_para]

    left_frame, right_frame = create_frames(w, h, margin=10, separation=10)
    left_frame.addFromList(left_flowables, my_canvas)
    right_frame.addFromList(right_flowables, my_canvas)
    draw_center_dotted_line(my_canvas)
    label = get_label(loan, styles)
    label_height = 20  # Assuming the height of the label, adjust as needed
    bottom_margin = 5 * mm  # Adjust based on your document's bottom margin

    # Calculate the y position for the label to be at the bottom of the frame
    label_y_position = bottom_margin + label_height

    label.wrapOn(my_canvas, (w / 2) - 15 * mm, h)
    # Adjust the y coordinate to position the label at the bottom
    label.drawOn(my_canvas, (w) / 2 + 5 * mm, label_y_position)

    my_canvas.showPage()

    # Recreate the frames for the second page
    left_frame, right_frame = create_frames(w, h, margin=10, separation=10)
    page3_flowables = page3(styles)
    page4_flowables = page4(styles)
    left_frame.addFromList(page3_flowables, my_canvas)
    right_frame.addFromList(page4_flowables, my_canvas)
    draw_center_dotted_line(my_canvas)

    my_canvas.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


def get_custom_jsk(loan):
    page_width = 14.6 * cm
    page_height = 21 * cm
    # Grid spacing
    grid_spacing = 1 * cm  # Adjust this value based on your preference
    buffer = io.BytesIO()
    c = Canvas(buffer, pagesize=(page_width, page_height))

    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(12 * cm, 18.5 * cm, f"{loan.lid}")
    c.drawString(11.5 * cm, 17.5 * cm, f"{loan.loan_date.strftime('%d-%m-%Y')}")

    styles = getSampleStyleSheet()

    customer = f"{loan.customer.name} {loan.customer.get_relatedas_display()} {loan.customer.relatedto}"
    customer_paragraph = Paragraph(customer, styles["Heading3"])
    # Calculate the width and height of the paragraph
    width, height = customer_paragraph.wrap(page_width, page_height)

    # Draw the paragraph on the canvas at the specified position
    customer_paragraph.drawOn(c, 2 * cm, 16 * cm - height)

    address = f"{loan.customer.address.first()}"
    address_paragraph = Paragraph(address, styles["Normal"])
    # Calculate the width and height of the paragraph
    width, height = address_paragraph.wrap(page_width, page_height)
    address_paragraph.drawOn(c, 2 * cm, 15 * cm - height)

    c.drawString(2 * cm, 14 * cm, f"Ph: {loan.customer.contactno.first()}")

    c.setFont("Helvetica", 8)
    weight = loan.formatted_weight(joiner=",")
    c.drawString(10 * cm, 11.8 * cm, f"{weight}gms ")
    pure = loan.formatted_pure(joiner=",")
    c.drawString(10 * cm, 9.8 * cm, f"{pure} gms ")
    c.drawString(10 * cm, 8 * cm, f"{loan.current_value()}")

    c.setFont("Helvetica-Bold", 14)

    data = [
        [
            "Description",
        ]
    ]
    for i, item in enumerate(loan.loanitems.all(), start=1):
        itemdesc = Paragraph(item.itemdesc, styles["Normal"])
        data.append(
            [
                f"{i}, {item.itemdesc}",
            ]
        )

    table = Table(data)
    table.setStyle(
        TableStyle(
            [
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.black),
            ]
        )
    )
    # Draw the table on the canvas at the specified position
    table.wrapOn(c, page_width / 2, page_height)
    table.drawOn(c, 2.5 * cm, 10.5 * cm)

    c.setFont("Helvetica-Bold", 12)
    c.drawString(8 * cm, 6.5 * cm, f"{loan.loan_amount}")
    amt_fig = num2words(loan.loan_amount, lang="en_IN")
    c.drawString(2 * cm, 6 * cm, f"{amt_fig} rupees only")
    c.showPage()

    c.setFont("Helvetica", 12)
    # Grid spacing
    grid_spacing = 1 * cm  # Adjust this value based on your preference

    c.drawString(3 * cm, 17.5 * cm, f"{loan.lid}")
    c.drawString(11 * cm, 17.5 * cm, f"{loan.loan_date.strftime('%d-%m-%Y')}")
    c.drawString(5 * cm, 17 * cm, f"{loan.customer.name}")
    c.drawString(
        5 * cm,
        16.5 * cm,
        f"{loan.customer.get_relatedas_display()} {loan.customer.relatedto}",
    )

    width, height = address_paragraph.wrap(page_width, page_height)
    address_paragraph.drawOn(c, 5 * cm, 16 * cm - height)
    c.drawString(5 * cm, 14 * cm, f"{loan.customer.contactno.first()}")
    c.drawString(5 * cm, 13.5 * cm, f"{loan.loan_amount}")

    c.drawString(5 * cm, 13 * cm, f"{amt_fig} rupees only")

    item_desc_paragraph = Paragraph(loan.item_desc, styles["Normal"])
    width, height = item_desc_paragraph.wrap(page_width, page_height)
    item_desc_paragraph.drawOn(c, 3 * cm, 11 * cm - height)

    c.setFont("Helvetica", 8)
    c.drawString(3 * cm, 7 * cm, f"{weight}gms")
    c.drawString(7 * cm, 7 * cm, f"{pure}")

    c.drawString(12 * cm, 7 * cm, f"{loan.current_value()}")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(1 * cm, 3.5 * cm, f"{loan.lid}")
    c.drawString(1 * cm, 3 * cm, f"{loan.loan_date.strftime('%d/%m/%y')}")
    c.drawString(1 * cm, 2.5 * cm, f"{loan.loan_amount}   {weight}")
    c.drawString(1 * cm, 2 * cm, f"{loan.customer.name}")

    item_desc_paragraph.drawOn(c, 1 * cm, 1.5 * cm - height)

    c.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


def on_all_pages(canvas, doc):
    canvas.saveState()
    canvas.setFont("Times-Roman", 10)
    canvas.drawString(inch, 0.75 * inch, "Page %d" % doc.page)
    canvas.restoreState()


def get_notice_pdf(selection=None):
    # TODO: paginate the pdf for better performance
    # TODO: add a progress bar
    # TODO: add page templates

    # Create a file-like buffer to receive PDF data.
    buffer = io.BytesIO()
    # Create the PDF object, using the buffer as its "file."
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    doc.title = "Notice-Group"

    # Define styles for the paragraphs
    styles = getSampleStyleSheet()
    top_style = ParagraphStyle(
        name="Normal_CENTER",
        parent=styles["Normal"],
        fontName="Helvetica",
        wordWrap="LTR",
        alignment=TA_CENTER,
        fontSize=12,
        leading=13,
        textColor=colors.black,
        borderPadding=0,
        leftIndent=0,
        rightIndent=0,
        spaceAfter=0,
        spaceBefore=0,
        splitLongWords=True,
        spaceShrinkage=0.05,
    )

    # Main story list
    story = []
    spacer = Spacer(0, 0.25 * inch)
    simple_tblstyle = TableStyle(
        [
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.black),
            ("BOX", (0, 0), (-1, -1), 0.25, colors.black),
        ]
    )

    # Iterate over selected loans
    for customer, loans in groupby(selection, key=lambda x: x.customer):
        # Grouped loans
        loans = list(loans)

        # Append paragraphs to the story
        story.extend(
            [
                spacer,
                Paragraph("TAMILNADU PAWNBROKERS ACT, 1943", top_style),
                spacer,
                Paragraph("NOTICE TO REDEEM PLEDGE", styles["Heading1"]),
                spacer,
                Paragraph(f"To,<br/>{customer}", styles["Normal"]),
                spacer,
                Paragraph(
                    "Notice is hereby given that the Pledge of the following article(s) is now "
                    "at the Pawn Broker named below, and that unless the same is redeemed within "
                    "30 days from the date hereof, it will be sold by public auction at the Pawn "
                    "Broker's place of business, without further notice to the Pledger or his agent."
                ),
                spacer,
                Paragraph(
                    "<br/>Name of Pawn Broker: J Champalal Pawn Brokers",
                    styles["Normal"],
                ),
                Paragraph("<br/>Description of Articles Pledged:", styles["Normal"]),
            ]
        )

        # Create table
        table_data = [["#", "Loan ID", "Created", "Item Weight", "Item Description"]]
        table_data.extend(
            [
                [
                    i + 1,
                    loan.loan_id,
                    loan.loan_date.date(),
                    loan.get_weight[0],
                    item.itemdesc,
                ]
                for i, (loan, item) in enumerate(
                    ((loan, item) for loan in loans for item in loan.loanitems.all())
                )
            ]
        )

        # Add table to the story
        f = Table(table_data)
        f.setStyle(simple_tblstyle)
        story.extend([spacer, f, PageBreak()])

    # Save the PDF and return the response
    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


def print_noticegroup(selection=None):
    pdf = get_notice_pdf(selection)
    response = HttpResponse(pdf, content_type="application/pdf")
    filename = "Notice-Group.pdf"
    content = "inline; filename='%s'" % (filename)
    download = request.GET.get("download")
    if download:
        content = "attachment; filename='%s'" % (filename)
    response["Content-Disposition"] = content
    return response


def print_labels_pdf(loans):
    # Create a file-like buffer to receive PDF data.
    buffer = io.BytesIO()

    width, height = 288, 144  # Page size for 4-inch wide, 2-inch high label
    c = canvas.Canvas(buffer, pagesize=(width, height))

    for i, loan in enumerate(loans):
        c.setFont("Helvetica", 12)
        c.drawString(30, height - 15, f"Loan ID: {loan.loan_id}")
        c.drawString(30, height - 30, f"Loan Date: {loan.loan_date.date()}")
        c.drawString(30, height - 45, f"Loan Amount: {loan.loan_amount}")
        c.drawString(30, height - 60, f"Weight: {loan.get_weight}")
        c.drawString(30, height - 75, f"Customer: {loan.customer.name}")
        c.drawString(30, height - 90, f"Item Description: {loan.item_desc}")

        # draw a QR code
        qr_code = qr.QrCodeWidget(loan.loan_id)
        bounds = qr_code.getBounds()
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]
        d = Drawing(45, 45, transform=[45.0 / width, 0, 0, 45.0 / height, 0, 0])
        d.add(qr_code)
        renderPDF.draw(d, c, 15, height - 105)
        c.showPage()  # Start a new page after each label

    c.save()

    # Create a new HTTP response with PDF data.
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = "inline; filename=labels.pdf"
    return response
