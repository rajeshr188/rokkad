import io
import os
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
from reportlab.platypus import (
    Flowable,
    Frame,
    FrameBreak,
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.doctemplate import PageTemplate

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.girvi.models import Loan


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
    centered_style = ParagraphStyle(
        name="Centered", parent=styles["Normal"], alignment=1
    )  # 1 is for center alignment

    # Generate the QR code
    qr_code_value = f"{loan.loan_id}"
    qr_code = qr.QrCodeWidget(qr_code_value)
    bounds = qr_code.getBounds()
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    d = Drawing(50, 50, transform=[50.0 / width, 0, 0, 50.0 / height, 0, 0])
    d.add(qr_code)

    # # Convert the QR code to an image
    # buffer = io.BytesIO()
    # renderPDF.drawToFile(d, buffer)
    # buffer.seek(0)
    # qr_code_image = Image(buffer, width=50, height=50)

    logo = Image("static/images/falconx.png", 50, 50)

    shop_license = loan.series.license
    customer = loan.customer
    customer_pic = None
    default_pic = customer.get_default_pic()
    if default_pic:
        customer_pic = Image(default_pic.path, 50, 50)
    
    header_data = [
        [
            Paragraph("Sec Rules 8", styles["Normal"]),
            Paragraph(
                f"Pawn Ticket <font name='NotoSansTamil-VariableFont_wdth,wght'>அடகு சீட்டு </font>",
                styles["Heading3"],
            ),
            Paragraph(""),
            Paragraph(f"{loan.series.license.name}", styles["Normal"]),
        ],
        [
            logo,
            [
                Paragraph(shop_license.shopname, styles["Heading3"]),
                Paragraph(
                    f"<font size=12>{shop_license.address}</font>", styles["Normal"]
                ),
                Paragraph(
                    f"<font size=10>Propreitor :{shop_license.propreitor}</font>",
                    styles["Normal"],
                ),
            ],
            "",
            d,
        ],
        [
            Paragraph(f"LoanId : <b>{loan.loan_id}</b>", styles["Normal"]),
            Paragraph(""),
            Paragraph(
                f"Date : <b>{loan.loan_date.strftime('%d-%m-%Y')}</b>", styles["Normal"]
            ),
        ],
        [Paragraph("Customer", styles["Heading3"])],
        [
            customer_pic,
            [
                Paragraph(
                    f"{customer.name} {customer.relatedas} {customer.relatedto}".title(),
                    centered_style,
                ),
                Paragraph(
                    f"""{loan.customer.address.first()}<br />ph:{loan.customer.contactno.first()}""",
                    centered_style,
                ),
            ],
        ],
        [Paragraph("Following article/s are pawned with me:", styles["Heading4"])],
    ]

    header = Table(header_data)
    header_style = TableStyle(
        [
            ("BOX", (0, 0), (-1, -1), 0.25, colors.black),
            ("SPAN", (0, 7), (-1, 7)),
            ("SPAN", (0, 8), (-1, 8)),
            ("SPAN", (0, 11), (-1, 11)),
            ("SPAN", (1, 0), (2, 0)),
            ("SPAN", (1, 1), (2, 1)),
            ("SPAN", (0, 3), (-1, 3)),
            ("SPAN", (0, 2), (1, 2)),
            ("SPAN", (2, 2), (3, 2)),
            ("SPAN", (1, 4), (-1, 4)),
            ("SPAN", (0, 5), (-1, 5)),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.black),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),  # Center-align text in all cells
            (
                "BACKGROUND",
                (1, 0),
                (1, 0),
                colors.grey,
            ),  # Set background color to grey for the second column of the first row
            (
                "TEXTCOLOR",
                (1, 0),
                (1, 0),
                colors.whitesmoke,
            ),  # Set text color to white for the second column of the first row
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
                            "Time agreed for redemption of pawned articles is 3 months.",
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
                    f"<font name='NotoSansTamil-VariableFont_wdth,wght'>3 மதத்திற்கு ஒரு முறை  தவறாமல் வட்டி செலுத்தவேண்டும்</font>",
                    normal,
                ),
                Paragraph(
                    f"<font name='NotoSansTamil-VariableFont_wdth,wght'>இந்த ரசித்து கொண்டுவந்ததால் தன பொருள் (அ ) நகை கொடுக்கப்படும் </font>",
                    normal,
                ),
                Paragraph(
                    f"<font name='NotoSansTamil-VariableFont_wdth,wght'>வியாபாரம் நேரம் :காலை  9:00 முதல் பகல் 1:00 மணி வரை ,பகல் 2:00 மணி முதல் மலை 7:00 மணி வரை  ஞாயுறு விடுமுறை .</font>",
                    normal,
                ),
                Paragraph(
                    f"<font name='NotoSansTamil-VariableFont_wdth,wght'>இந்த ரசித்து பிறர் வசம்  கொடுக்கக்கூடாது</font>",
                    normal,
                ),
                Paragraph(
                    f"<font name='NotoSansTamil-VariableFont_wdth,wght'>ஒரு வருடம் 7 நாட்களுக்குமேல் தாங்கள் அடகு வாய்த்த பொருட்கள் ஏல்லத்தில் விட படும்</font>",
                    normal,
                ),
                Paragraph(
                    f"<font name='NotoSansTamil-VariableFont_wdth,wght'>குறிப்பு: மதத்திற்கு அவ்வளவு நாட்கள் குறையினும் முழு மாத வட்டி செலுத்தவேண்டும் .நீங்கள் வரு இடம் போகும் பட்சத்தில் விலாசம் தெரிவிக்க வேண்டும்.</font>",
                    normal,
                ),
                Paragraph(
                    f"<font name='NotoSansTamil-VariableFont_wdth,wght'>இதில் கண்ட நகைகள் சரிபாத்து பெற்றுக்கொண்டேன் .</font>",
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
    d3 = """<font name='NotoSansTamil-VariableFont_wdth,wght'>
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

    right_flowables_page2 = [
        Paragraph(
            f"D3 <font name='NotoSansTamil-VariableFont_wdth,wght'> படிவம்</font>",
            centeredHeading2,
        ),
        Paragraph(f"{d3}", styles["Normal"]),
    ]

    return right_flowables_page2


def get_loan_template(loan):
    pdfmetrics.registerFont(
        TTFont(
            "NotoSansTamil-VariableFont_wdth,wght",
            "static/fonts/NotoSansTamil-VariableFont_wdth,wght.ttf",
        ),
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
    customer_paragraph.drawOn(c, 5 * cm, 16 * cm - height)

    # Load the customer image from the ImageField
    # customer_image_path = (
    #     loan.customer.get_default_pic().path
    # )  # Use .path to get the file system path
    customer_pic = None
    default_pic = loan.customer.get_default_pic()
    if default_pic:
        customer_pic = Image(default_pic.path, 50, 50)

    
        # Set the desired dimensions for the image (e.g., 5x5 cm)
        desired_width = 2.5 * cm
        desired_height = 2.5 * cm

        # Calculate the position for the image
        image_x = 2 * cm
        image_y = 16 * cm - desired_height

        # Draw the image on the canvas
        customer_image = Image(
            default_pic, width=desired_width, height=desired_height
        )
        customer_image.drawOn(c, image_x, image_y)

        # Draw a border around the image
        border_padding = 2  # Padding around the image for the border
        c.setStrokeColorRGB(0, 0, 0)  # Set the border color (black)
        c.setLineWidth(1)  # Set the border width
        c.rect(
            image_x - border_padding,
            image_y - border_padding,
            desired_width + 2 * border_padding,
            desired_height + 2 * border_padding,
        )

    address = f"{loan.customer.address.first()}"
    address_paragraph = Paragraph(address, styles["Normal"])
    # Calculate the width and height of the paragraph
    width, height = address_paragraph.wrap(page_width, page_height)
    address_paragraph.drawOn(c, 5 * cm, 15 * cm - height)

    c.drawString(5 * cm, 14 * cm, f"Ph: {loan.customer.contactno.first()}")

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


# form_letter.py

import time

from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer


def form_letter():
    doc = SimpleDocTemplate(
        "form_letter.pdf",
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18,
    )
    flowables = []
    # logo = "python_logo.png"
    magName = "Pythonista"
    issueNum = 12
    subPrice = "99.00"
    limitedDate = "03/05/2010"
    freeGift = "tin foil hat"

    formatted_time = time.ctime()
    full_name = "Mike Driscoll"
    address_parts = ["411 State St.", "Waterloo, IA 50158"]

    # im = Image(logo, 2*inch, 2*inch)
    # flowables.append(im)

    styles = getSampleStyleSheet()
    # Modify the Normal Style
    styles["Normal"].fontSize = 12
    styles["Normal"].leading = 14

    # Create a Justify style
    styles.add(ParagraphStyle(name="Justify", alignment=TA_JUSTIFY))

    flowables.append(Paragraph(formatted_time, styles["Normal"]))
    flowables.append(Spacer(1, 12))

    # Create return address
    flowables.append(Paragraph(full_name, styles["Normal"]))
    for part in address_parts:
        flowables.append(Paragraph(part.strip(), styles["Normal"]))

    flowables.append(Spacer(1, 12))
    ptext = "Dear {}:".format(full_name.split()[0].strip())
    flowables.append(Paragraph(ptext, styles["Normal"]))
    flowables.append(Spacer(1, 12))

    ptext = """
    We would like to welcome you to our subscriber
    base for {magName} Magazine! You will receive {issueNum} issues at
    the excellent introductory price of ${subPrice}. Please respond by
    {limitedDate} to start receiving your subscription and get the
    following free gift: {freeGift}.
    """.format(
        magName=magName,
        issueNum=issueNum,
        subPrice=subPrice,
        limitedDate=limitedDate,
        freeGift=freeGift,
    )
    flowables.append(Paragraph(ptext, styles["Justify"]))
    flowables.append(Spacer(1, 12))

    ptext = """Thank you very much and we look
    forward to serving you."""

    flowables.append(Paragraph(ptext, styles["Justify"]))
    flowables.append(Spacer(1, 12))
    ptext = "Sincerely,"
    flowables.append(Paragraph(ptext, styles["Normal"]))
    flowables.append(Spacer(1, 48))
    ptext = "Ima Sucker"
    flowables.append(Paragraph(ptext, styles["Normal"]))
    flowables.append(Spacer(1, 12))
    doc.build(flowables)


def generate_form_a():
    # Form A [See Section 4 (1) and rule 3] Form of Application For A Pawnbroker's Licence To The Tahsildar, Independent Deputy Tahsildar,  .........Taluk                                                                                        1. Name in full of the applicant. 2. Address in full (any subsequent change should be notified). 3. Father's name. 4. Is the applicant a citizen of India? If the applicant has a residence outside the State of Tamil Nadu (1) Full address of such residence; and (2) A list of the properties owned by him in places outside the State of Tamil Nadu. 5. Address of shop or place of business in respect of which the licence is applied for. 6. If the applicant has more than one shop or place of business, the address of each such shop or place of business. 7. Has the applicant applied for a separate licence in respect of each shop or place of business mentioned against item 6, and if so, with what result? 8. Is the present application made for the grant of a new licence or for the renewal of a licence granted in the previous year? 9. The financial year for which the licence is applied for. 10. Has the applicant paid the prescribed fee for the licence. (The treasury receipt should be enclosed).      Passport size         photograph to be         affixed by the         applicant and         attested by the        licensing           authority.)   11. Name of the nominee with actress: (a) Age and sex. (b) Amount of solvency. (c) Is the nominee's consent letter mentioned in rule 3(2) attached ? I declare that the particulars stated above are correct to the best of my knowledge and belief.                                                                                       Signature of the applicant.  Annexure Specimen signatures of the applicant: (1)........... (2)........... (3)........... (The specimen signatures should be attested by the licensing authority)

    # Create a SimpleDocTemplate
    doc = SimpleDocTemplate("pawnbroker_application_form.pdf", pagesize=letter)

    # Get the sample stylesheet
    styles = getSampleStyleSheet()

    # Define the content
    form_a_content = """
    <b>Form A </b><br/>
    [See Section 4 (1) and rule 3]<br/>
    <b>Form of Application For A Pawnbroker's Licence</b><br/>
    To The Tahsildar, Independent Deputy Tahsildar, .........Taluk<br/>
    <br/>
    1. Name in full of the applicant.<br/>
    2. Address in full (any subsequent change should be notified).<br/>
    3. Father's name.<br/>
    4. Is the applicant a citizen of India?<br/>
    If the applicant has a residence outside the State of Tamil Nadu<br/>
    (1) Full address of such residence; and<br/>
    (2) A list of the properties owned by him in places outside the State of Tamil Nadu.<br/>
    5. Address of shop or place of business in respect of which the licence is applied for.<br/>
    6. If the applicant has more than one shop or place of business, the address of each such shop or place of business.<br/>
    7. Has the applicant applied for a separate licence in respect of each shop or place of business mentioned against item 6, and if so, with what result?<br/>
    8. Is the present application made for the grant of a new licence or for the renewal of a licence granted in the previous year?<br/>
    9. The financial year for which the licence is applied for.<br/>
    10. Has the applicant paid the prescribed fee for the licence. (The treasury receipt should be enclosed).<br/>
    <br/>
    <i>Passport size photograph to be affixed by the applicant and attested by the licensing authority.</i><br/>
    <br/>
    11. Name of the nominee with address:<br/>
    (a) Age and sex.<br/>
    (b) Amount of solvency.<br/>
    (c) Is the nominee's consent letter mentioned in rule 3(2) attached?<br/>
    <br/>
    I declare that the particulars stated above are correct to the best of my knowledge and belief.<br/>
    <br/>
    Signature of the applicant.<br/>
    <br/>
    <b>Annexure</b><br/>
    Specimen signatures of the applicant:<br/>
    (1)...........<br/>
    (2)...........<br/>
    (3)...........<br/>
    <i>(The specimen signatures should be attested by the licensing authority)</i>
    """

    # Create a Paragraph object
    paragraph = Paragraph(content, styles["Normal"])

    # List of flowable elements
    elements = [paragraph, Spacer(1, 12)]

    # Build the PDF
    doc.build(elements)


def generate_form_c():
    # declaration by pawner,Transfer of owvership
    # Form C [See section 8(2) and rule 6(1)] Declaration by Fawner Tahsildar of .............. taluk -------------------------------------------- Independent Deputy Tahsildar. I,.........of........in pursuance of subjection (2) of section 8 of the Tamil Nadu Pawnbrokers Act, 1943 (Tamil Nadu Act XXIII of 1943), do solemnly and sincerely declare that the right to redeem the article/articles described below pawned by me at the shop of.............Pawnbroker and covered by Pawn Ticket No............dated..........has been transferred to or is vested in and that is entitled to redeem the pledge. I also hereby declare that my right to redeem the pledge is hereby extinguished. The article/articles above referred to is/are of the following description: - 1........... 2........... Signature of the pawner. Designation. Address. Date. I, .........of........... in pursuance of sub-section (2) of section 8 of the said Act do solemnly and sincerely declare that I know the person now making the foregoing declaration to be..........of........... Signature of identifying person. Designation. Address. Date.

    # Create a SimpleDocTemplate
    doc = SimpleDocTemplate("loan_declaration.pdf", pagesize=letter)

    # Get the sample stylesheet
    styles = getSampleStyleSheet()

    # Define the content
    content = """
    <b>Form C [See section 8(2) and rule 6(1)]</b><br/>
    Declaration by Fawner Tahsildar of .............. taluk<br/>
    --------------------------------------------<br/>
    Independent Deputy Tahsildar.<br/>
    I,.........of........in pursuance of subjection (2) of section 8 of the Tamil Nadu Pawnbrokers Act, 1943 (Tamil Nadu Act XXIII of 1943), do solemnly and sincerely declare that the right to redeem the article/articles described below pawned by me at the shop of.............Pawnbroker and covered by Pawn Ticket No............dated..........has been transferred to or is vested in and that is entitled to redeem the pledge. I also hereby declare that my right to redeem the pledge is hereby extinguished.<br/>
    The article/articles above referred to is/are of the following description:<br/>
    1...........<br/>
    2...........<br/>
    <br/>
    Signature of the pawner.<br/>
    Designation.<br/>
    Address.<br/>
    Date.<br/>
    <br/>
    I, .........of........... in pursuance of sub-section (2) of section 8 of the said Act do solemnly and sincerely declare that I know the person now making the foregoing declaration to be..........of...........<br/>
    <br/>
    Signature of identifying person.<br/>
    Designation.<br/>
    Address.<br/>
    Date.
    """

    # Create a Paragraph object
    paragraph = Paragraph(content, styles["Normal"])

    # List of flowable elements
    elements = [paragraph, Spacer(1, 12)]

    # Build the PDF
    doc.build(elements)


def generate_form_d():
    # Form D [See section 8(2) and rule 6(1)] Declaration by the Person Entitled to Redeem The Pledge I,........of.........in pursuance of sub-section (2) of section 8 of the Tamil Nadu Pawnbrokers Act, 1943 (Tamil Nadu Act XXIII of 1943), do solemnly and sincerely declare that the right to redeem the article/articles described below, the property of, and pawned by,........... at the shop of pawnbroker and covered by .............. Pawn Ticket No............... has been transferred to or is vested in me. I also do solemnly and sincerely declare that I am in possession of the said Pawn Ticket and that I am entitled to redeem the pledge. The article/articles above referred to is/are of the following description: - 1........... 2........... Signature of the pawner. Designation. Address. Date. I,........of.........in pursuance of sub-section (2) of section 8 of the said Act, to solemnly and sincerely declare that I know the person now making the foregoing declaration to be of...............of................ Signature of identifying person. Designation. Address. Date.

    # Create a SimpleDocTemplate
    doc = SimpleDocTemplate("declaration_form_d.pdf", pagesize=letter)

    # Get the sample stylesheet
    styles = getSampleStyleSheet()

    # Define the content
    content = """
    <b>Form D [See section 8(2) and rule 6(1)]</b><br/>
    Declaration by the Person Entitled to Redeem The Pledge<br/>
    I,........of.........in pursuance of sub-section (2) of section 8 of the Tamil Nadu Pawnbrokers Act, 1943 (Tamil Nadu Act XXIII of 1943), do solemnly and sincerely declare that the right to redeem the article/articles described below, the property of, and pawned by,........... at the shop of pawnbroker and covered by .............. Pawn Ticket No............... has been transferred to or is vested in me. I also do solemnly and sincerely declare that I am in possession of the said Pawn Ticket and that I am entitled to redeem the pledge.<br/>
    The article/articles above referred to is/are of the following description:<br/>
    1...........<br/>
    2...........<br/>
    <br/>
    Signature of the pawner.<br/>
    Designation.<br/>
    Address.<br/>
    Date.<br/>
    <br/>
    I,........of.........in pursuance of sub-section (2) of section 8 of the said Act, to solemnly and sincerely declare that I know the person now making the foregoing declaration to be of...............of................<br/>
    <br/>
    Signature of identifying person.<br/>
    Designation.<br/>
    Address.<br/>
    Date.
    """

    # Create a Paragraph object
    paragraph = Paragraph(content, styles["Normal"])

    # List of flowable elements
    elements = [paragraph, Spacer(1, 12)]

    # Build the PDF
    doc.build(elements)


def generate_form_d1():
    # Form D-1 [See section 8(3) and rule 6(1)] Declaration by Messenger/Agent I,........of.........in pursuance of sub-section (3) of section 8 of the Tamil Nadu Pawnbrokers Act, 1943 (Tamil Nadu Act XXIII of 1943), solemnly and sincerely declare that I am the messenger/agent of the pawner who has pawned the article/articles described below at the shop of.......... pawnbroker under Pawn Ticket No.............dated.........and that I have been duly authorized by the pawner to redeem the pledge. The article/articles above referred to is/are of the following description: - 1........... 2........... Signature of the messenger/agent. Designation. Address. Date. I,.........of..........in pursuance of sub-section (3) of section 8 of the said Act, do solemnly and sincerely declare that I know the person now making the above declaration. Signature of identifying person. Designation. Address. Date.

    # Create a SimpleDocTemplate
    doc = SimpleDocTemplate("form_d1.pdf", pagesize=letter)

    # Get the sample stylesheet
    styles = getSampleStyleSheet()

    # Define the content
    content = """
    <b>Form D-1 [See section 8(3) and rule 6(1)]</b><br/>
    <b>Declaration by Messenger/Agent</b><br/>
    I,........of.........in pursuance of sub-section (3) of section 8 of the Tamil Nadu Pawnbrokers Act, 1943 (Tamil Nadu Act XXIII of 1943), solemnly and sincerely declare that I am the messenger/agent of the pawner who has pawned the article/articles described below at the shop of.......... pawnbroker under Pawn Ticket No.............dated.........and that I have been duly authorized by the pawner to redeem the pledge.<br/>
    <br/>
    The article/articles above referred to is/are of the following description:<br/>
    1...........<br/>
    2...........<br/>
    <br/>
    Signature of the messenger/agent.<br/>
    Designation.<br/>
    Address.<br/>
    Date.<br/>
    <br/>
    I,.........of..........in pursuance of sub-section (3) of section 8 of the said Act, do solemnly and sincerely declare that I know the person now making the above declaration.<br/>
    <br/>
    Signature of identifying person.<br/>
    Designation.<br/>
    Address.<br/>
    Date.
    """

    # Create a list to hold the flowable elements
    flowables = []

    # Create a Paragraph object and add it to the flowables list
    flowables.append(Paragraph(content, styles["Normal"]))

    # Add a spacer for spacing
    flowables.append(Spacer(1, 12))

    # Build the PDF
    doc.build(flowables)


def generate_form_d2():
    # Form D-2 [See section 8(4)(a)(i) and rule 6(1)] Declaration by Legal Representative of Pawner I,........ of.......... in pursuance of sub-clause (i) of clause (a) of sub-section (4) of section 8 of the Tamil Nadu Pawnbrokers Act, 1943 (Tamil Nadu Act XXIII of 1943), do solemnly and sincerely declare that I am the legal representative of deceased pawner being his/her ..........and that I am entitled to redeem the article/articles described below and pawned by the deceased pawner at the shop of pawnbroker under Pawn Ticket No............... dated.......... I also hereby declare that the said Pawn Ticket is now in my possession. The article/articles above referred to is/are of the following description:- 1........... 2........... Signature of person. Designation. Address. Date. I,.........of......... in pursuance of sub-clause (i) of clause (a) of sub-section (4) of section 8 of the said Act, do solemnly and sincerely declare that I know the person now making foregoing declaration to be.........of......... Signature of identifying person. Designation. Address. Date. Declared before me this day of.......... Magistrate or Judge.

    # Create a SimpleDocTemplate
    doc = SimpleDocTemplate("form_d2.pdf", pagesize=letter)

    # Get the sample stylesheet
    styles = getSampleStyleSheet()

    # Define the content
    content = """
    <b>Form D-2 [See section 8(4)(a)(i) and rule 6(1)]</b><br/>
    <b>Declaration by Legal Representative of Pawner</b><br/>
    I,........ of.......... in pursuance of sub-clause (i) of clause (a) of sub-section (4) of section 8 of the Tamil Nadu Pawnbrokers Act, 1943 (Tamil Nadu Act XXIII of 1943), do solemnly and sincerely declare that I am the legal representative of deceased pawner being his/her ..........and that I am entitled to redeem the article/articles described below and pawned by the deceased pawner at the shop of pawnbroker under Pawn Ticket No............... dated.......... I also hereby declare that the said Pawn Ticket is now in my possession.<br/>
    <br/>
    The article/articles above referred to is/are of the following description:-<br/>
    1...........<br/>
    2...........<br/>
    <br/>
    Signature of person.<br/>
    Designation.<br/>
    Address.<br/>
    Date.<br/>
    <br/>
    I,.........of......... in pursuance of sub-clause (i) of clause (a) of sub-section (4) of section 8 of the said Act, do solemnly and sincerely declare that I know the person now making foregoing declaration to be.........of.........<br/>
    <br/>
    Signature of identifying person.<br/>
    Designation.<br/>
    Address.<br/>
    Date.<br/>
    <br/>
    Declared before me this day of..........<br/>
    Magistrate or Judge.
    """

    # Create a list to hold the flowable elements
    flowables = []

    # Create a Paragraph object and add it to the flowables list
    flowables.append(Paragraph(content, styles["Normal"]))

    # Add a spacer for spacing
    flowables.append(Spacer(1, 12))

    # Build the PDF
    doc.build(flowables)


def generate_form_d3():
    # Form D-3 [See section 8(6) and rule 6(1)] Declaration by Pawner of Loss or Destruction of Pawn Ticket I,........of...........in pursuance's of sub-section (6) of section 8 of the Tamil Nadu Pawnbrokers Act, 1943 (Tamil Nadu Act XXIII of 1943), do solemnly and sincerely declare that I pledged at shop of ................. pawnbroker, the article/article's described below being my property and having received a pawn ticket bearing No.............. dated ......... (if known) for the same which has since been lost/destroyed "and that the pawn ticket has not been sold, assigned or transferred to any person by me to the best of my knowledge and belief. The article/articles above referred to is/are of the following description: - 1.......... 2.......... Signature of the pawner. Designation. Address. Date. I,........of.......in pursuance of sub-section (6) of section 8 of the said Act, do solemnly and sincerely declare that I know the person making the foregoing declaration........... to be................ of............... Signature of identifying person. Designation. Address. Date.

    # Create a SimpleDocTemplate
    doc = SimpleDocTemplate("form_d3.pdf", pagesize=letter)

    # Get the sample stylesheet
    styles = getSampleStyleSheet()

    # Define the content
    content = """
    <b>Form D-3 [See section 8(6) and rule 6(1)]</b><br/>
    <b>Declaration by Pawner of Loss or Destruction of Pawn Ticket</b><br/>
    I,........of...........in pursuance's of sub-section (6) of section 8 of the Tamil Nadu Pawnbrokers Act, 1943 (Tamil Nadu Act XXIII of 1943), do solemnly and sincerely declare that I pledged at shop of ................. pawnbroker, the article/article's described below being my property and having received a pawn ticket bearing No.............. dated ......... (if known) for the same which has since been lost/destroyed "and that the pawn ticket has not been sold, assigned or transferred to any person by me to the best of my knowledge and belief.<br/>
    <br/>
    The article/articles above referred to is/are of the following description:-<br/>
    1..........<br/>
    2..........<br/>
    <br/>
    Signature of the pawner.<br/>
    Designation.<br/>
    Address.<br/>
    Date.<br/>
    <br/>
    I,........of.......in pursuance of sub-section (6) of section 8 of the said Act, do solemnly and sincerely declare that I know the person making the foregoing declaration........... to be................ of...............<br/>
    <br/>
    Signature of identifying person.<br/>
    Designation.<br/>
    Address.<br/>
    Date.
    """

    # Create a list to hold the flowable elements
    flowables = []

    # Create a Paragraph object and add it to the flowables list
    flowables.append(Paragraph(content, styles["Normal"]))

    # Add a spacer for spacing
    flowables.append(Spacer(1, 12))

    # Build the PDF
    doc.build(flowables)


def generate_form_h(release):
    # create a buffer to hold the PDF
    buffer = BytesIO()
    # Create a SimpleDocTemplate
    doc = SimpleDocTemplate(buffer, pagesize=letter)

    # Get the sample stylesheet
    styles = getSampleStyleSheet()
    centered_style = ParagraphStyle(
        name="Centered", parent=styles["Normal"], alignment=1
    )  # 1 is for center alignment

    # Define the table data with placeholders

    data = [
        [
            Paragraph("Form H", centered_style),
            Paragraph("Receipt", centered_style),
            Paragraph("P.B.L No: ", centered_style),
            Paragraph(f"{release.loan.series.license.name}", centered_style),
        ],
        [Paragraph("[See section 10(l)(b)(v) and rule 8]", centered_style), "", "", ""],
        [
            Paragraph(
                f"<b>{release.loan.series.license.shopname}</b><br/>{release.loan.series.license.address}",
                centered_style,
            ),
            "",
            "",
            "",
        ],
        ["ReleaseId", f"{release.id}", "Date:", f"{release.release_date.date()}"],
        ["Received from", f"{release.released_by.name}", "", ""],
        [
            "On Pledge No",
            f"{release.loan.loan_id}",
            "Date",
            f"{release.loan.loan_date.date()}",
        ],
        [
            Paragraph("and received the articles in full satisfaction", centered_style),
            "",
            "",
            "",
        ],
        ["Amount of Loan Rs: ", "", f"{release.loan.loan_amount}", ""],
        ["Interest", "", f"{release.loan.interestdue()}", ""],
        [Paragraph("Total", centered_style), "", f"{release.loan.total()}", ""],
        ["", "", "", ""],
        [
            Paragraph("Signature ", centered_style),
            "",
            Paragraph("Sign of pawnbroker/his agent.", centered_style),
            "",
        ],
    ]

    # Create a list to hold the flowable elements
    flowables = []

    # Create the table
    table = Table(data)

    # Apply styles to the table
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                # ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ("SPAN", (0, 1), (-1, 1)),
                ("SPAN", (0, 2), (-1, 2)),
                ("SPAN", (1, 4), (3, 4)),
                ("SPAN", (0, 6), (-1, 6)),
                ("SPAN", (0, 7), (1, 7)),
                ("SPAN", (0, 8), (1, 8)),
                ("SPAN", (0, 9), (1, 9)),
                ("SPAN", (2, 7), (3, 7)),
                ("SPAN", (2, 8), (3, 8)),
                ("SPAN", (2, 9), (3, 9)),
                ("SPAN", (0, 10), (1, 10)),
                ("SPAN", (2, 10), (3, 10)),
                ("SPAN", (0, 11), (1, 11)),
                ("SPAN", (2, 11), (3, 11)),
            ]
        )
    )

    # Add the table to the flowables list
    flowables.append(table)
    # flowables.append(Paragraph("hello", styles["Normal"]))
    # Build the PDF
    doc.build(flowables)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


# Form D-4 [See section 8(7) and rule 6(1)] Declaration by Person Claiming to Be Owners of pledge I,........of.......in pursuance of sub-section (7) of section 8 of the Tamil Nadu Pawnbrokers Act, 1943 (Tamil Nadu Act XXIII of 1943), do solemnly and sincerely declare that I am the owner of the article/articles described below, pawned at shop of......... pawnbroker and that the pledge in respect of the article/articles was pawned without my knowledge or authority. The article/articles above referred to is/are of the following description: - 1........... 2........... Signature of person. Designation. Address. Date. I,..........of.......in pursuance of sub-section (7) of section 8 of the Act, do solemnly and sincerely declare that I know the person making the foregoing declaration to be......... of............ Signature of identifying person. Designation. Address. Date.
# Form D-5 [See second proviso to section 8(3) and rule 6(2)] Notice To The Pawner Notice is hereby given that ............. claiming himself to be your agent /messenger has produced on............ the pawn Ticket No dated............... issued to you for the article /articles described below pawned by you at my shop and offered to redeem the pledge. I, ............. pawnbroker propose to allow his/her claim to redeem, the pledge. You are hereby required to state your objections, if any, in respect of the above proposal. If nothing is heard from you within two weeks after the date on which this notice would in the usual course of post reach you, the person claiming to be your messenger/ agent will be allowed to redeem the pledge. The article/articles above referred to is/are of the following description:- 1........... 2........... Signature of pawnbroker. Address. Date.
# Form D-6 [See section 8(5) and rule 6(2)] Notice of Assignment To Pawnbroker Date. Notice is hereby given that I, ......... of .......... have come into possession of the pawn ticket No............dated.........as the assignee of the pawner by him at the shop of pawnbroker. You are hereby required to recognize my claim and to allow me to redeem the pledge. The article/articles above referred to is/are of the following description: - Description of the article/articles. Signature of the person. Designation. Address. Date. To Pawnbroker at..........
# Form D-7 [See section 8(5) and rule 6(2)] Notice To Pawner of Claim Made by Assignee Notice is hereby given that............claiming himself to be your assignee has produced on ................ the pawn ticket No............. dated............. given to you in respect of the article /articles described below pawned by you at the shop of........pawnbroker and he offered to redeem the pledge. I,........pawnbroker, propose to recognize his claim and to allow him to redeem pledge. You are hereby required to intimate to me the objections, if any, to the proposal. If nothing is heard from you within two weeks after the date on which this notice would in the usual course of post reach you, it will be presumed that you have no objection to the proposal and the claimant will be recognised as your assignee and allowed to redeem the pledge. The article/articles above referred to is /are of the following description. Description of the article/articles ............ ............ Signature of the pawnbroker. Address. Date.
# Form D-8 [See section 8(7) and rule 6(2)] Notice To Pawner of Claim by Owner of Pledge Date. Notice is hereby given that..........claims to the owner of the pledge in respect of the article /articles described below pawned at the shop........ of...........pawnbroker, and covered by pawn ticket No.............dated........... alleges that the pledge was pawned without his knowledge and authority. You are hereby required to intimate in writing whether you have any objection to the claim.......... or to the articles pledged by you. If no communication is received in writing within two weeks after the date on which it would in the usual course of post reach you, it will be presumed that you do not object to the claim made by the said.......... and he will be recognized as the legitimate owner of the article/articles and will be allowed to redeem the pledge. The article/articles above referred to is/are of the following description:- Description of the article/articles. ....................... ....................... ....................... Signature of the pawnbroker. Address. Date.
# Form G [See section 10(i)(b)(ii) and rule 8] Sale Book of Pledges (Date and place of sale) (Name and place of business of auctioneer) 1. Name of pledge as in the pledge book. 2. Date of pawning. 3. Name of pawner. 4. Amount of loan. 5. Amount for which pledge sold as stated by the auctioneer. 6. Signature of the auctioneer or his agent. 7. Name and address of purchaser.
# Form H [See section 10(l)(b)(v) and rule 8] Receipt Received from ............amount of loan........... on redemption of pledge, number........Interest Date. ----------- Total                 ----------- Signature of pawnbroker or his agent.
# Form I Certificate of The Pawnbroker or his Agent Under Rule 9 I certify that the above is a true copy of the account maintained under clause (a) of sub-section (1) of section 10 of the Tamil Nadu Pawnbrokers Act, 1943 (Tamil Nadu Act XXIII of 1943), for the loan of Rs.......... taken by .........on...........(date) and that there are no alterations or erasures in the account (except the following). Signature of pawnbroker or his agent.


def generate_pdf(content, filename):
    # Create a SimpleDocTemplate
    doc = SimpleDocTemplate(filename, pagesize=letter)

    # Get the sample stylesheet
    styles = getSampleStyleSheet()

    # Create a list to hold the flowable elements
    flowables = []

    # Create a Paragraph object and add it to the flowables list
    flowables.append(Paragraph(content, styles["Normal"]))

    # Add a spacer for spacing
    flowables.append(Spacer(1, 12))

    # Build the PDF
    doc.build(flowables)


# Define the content for each form
form_d4_content = """
                    <b>Form D-4 [See section 8(7) and rule 6(1)]</b><br/>
                    <b>Declaration by Person Claiming to Be Owners of pledge</b><br/>
                    I,........of.......in pursuance of sub-section (7) of section 8 of the Tamil Nadu Pawnbrokers Act, 1943 (Tamil Nadu Act XXIII of 1943), do solemnly and sincerely declare that I am the owner of the article/articles described below, pawned at shop of......... pawnbroker and that the pledge in respect of the article/articles was pawned without my knowledge or authority.<br/>
                    <br/>
                    The article/articles above referred to is/are of the following description:<br/>
                    1...........<br/>
                    2...........<br/>
                    <br/>
                    Signature of person.<br/>
                    Designation.<br/>
                    Address.<br/>
                    Date.<br/>
                    <br/>
                    I,..........of.......in pursuance of sub-section (7) of section 8 of the Act, do solemnly and sincerely declare that I know the person making the foregoing declaration to be......... of............<br/>
                    <br/>
                    Signature of identifying person.<br/>
                    Designation.<br/>
                    Address.<br/>
                    Date.
                    """

form_d5_content = """
                    <b>Form D-5 [See second proviso to section 8(3) and rule 6(2)]</b><br/>
                    <b>Notice To The Pawner</b><br/>
                    Notice is hereby given that ............. claiming himself to be your agent /messenger has produced on............ the pawn Ticket No dated............... issued to you for the article /articles described below pawned by you at my shop and offered to redeem the pledge. I, ............. pawnbroker propose to allow his/her claim to redeem, the pledge. You are hereby required to state your objections, if any, in respect of the above proposal. If nothing is heard from you within two weeks after the date on which this notice would in the usual course of post reach you, the person claiming to be your messenger/ agent will be allowed to redeem the pledge.<br/>
                    <br/>
                    The article/articles above referred to is/are of the following description:<br/>
                    1...........<br/>
                    2...........<br/>
                    <br/>
                    Signature of pawnbroker.<br/>
                    Address.<br/>
                    Date.
                    """

form_d6_content = """
                    <b>Form D-6 [See section 8(5) and rule 6(2)]</b><br/>
                    <b>Notice of Assignment To Pawnbroker</b><br/>
                    Date.<br/>
                    Notice is hereby given that I, ......... of .......... have come into possession of the pawn ticket No............dated.........as the assignee of the pawner by him at the shop of pawnbroker. You are hereby required to recognize my claim and to allow me to redeem the pledge.<br/>
                    <br/>
                    The article/articles above referred to is/are of the following description:<br/>
                    Description of the article/articles.<br/>
                    <br/>
                    Signature of the person.<br/>
                    Designation.<br/>
                    Address.<br/>
                    Date.<br/>
                    To Pawnbroker at..........
                    """

form_d7_content = """
                    <b>Form D-7 [See section 8(5) and rule 6(2)]</b><br/>
                    <b>Notice To Pawner of Claim Made by Assignee</b><br/>
                    Notice is hereby given that............claiming himself to be your assignee has produced on ................ the pawn ticket No............. dated............. given to you in respect of the article /articles described below pawned by you at the shop of........pawnbroker and he offered to redeem the pledge. I,........pawnbroker, propose to recognize his claim and to allow him to redeem pledge. You are hereby required to intimate to me the objections, if any, to the proposal. If nothing is heard from you within two weeks after the date on which this notice would in the usual course of post reach you, it will be presumed that you have no objection to the proposal and the claimant will be recognised as your assignee and allowed to redeem the pledge.<br/>
                    <br/>
                    The article/articles above referred to is /are of the following description.<br/>
                    Description of the article/articles<br/>
                    ............<br/>
                    ............<br/>
                    <br/>
                    Signature of the pawnbroker.<br/>
                    Address.<br/>
                    Date.
                    """

form_d8_content = """
                <b>Form D-8 [See section 8(7) and rule 6(2)]</b><br/>
                <b>Notice To Pawner of Claim by Owner of Pledge</b><br/>
                Date.<br/>
                Notice is hereby given that..........claims to the owner of the pledge in respect of the article /articles described below pawned at the shop........ of...........pawnbroker, and covered by pawn ticket No.............dated........... alleges that the pledge was pawned without his knowledge and authority. You are hereby required to intimate in writing whether you have any objection to the claim.......... or to the articles pledged by you. If no communication is received in writing within two weeks after the date on which it would in the usual course of post reach you, it will be presumed that you do not object to the claim made by the said.......... and he will be recognized as the legitimate owner of the article/articles and will be allowed to redeem the pledge.<br/>
                <br/>
                The article/articles above referred to is/are of the following description:<br/>
                Description of the article/articles.<br/>
                .......................<br/>
                .......................<br/>
                .......................<br/>
                <br/>
                Signature of the pawnbroker.<br/>
                Address.<br/>
                Date.
                """

form_g_content = """
                <b>Form G [See section 10(i)(b)(ii) and rule 8]</b><br/>
                <b>Sale Book of Pledges</b><br/>
                (Date and place of sale)<br/>
                (Name and place of business of auctioneer)<br/>
                1. Name of pledge as in the pledge book.<br/>
                2. Date of pawning.<br/>
                3. Name of pawner.<br/>
                4. Amount of loan.<br/>
                5. Amount for which pledge sold as stated by the auctioneer.<br/>
                6. Signature of the auctioneer or his agent.<br/>
                7. Name and address of purchaser.
                """

form_h_content = """
            <b>Form H <br />
            [See section 10(l)(b)(v) and rule 8]</b><br/>
            <b>Receipt</b>    P.B.L No: {{license__name}}<br/>
            <b>{{company_name}}</b><br/>
            <b></b>
            Received from ............amount of loan........... on redemption of pledge, number........Interest Date.<br/>
            -----------<br/>
            Total<br/>
            -----------<br/>
            Signature of pawnbroker or his agent.
            """

form_i_content = """
            <b>Form I Certificate of The Pawnbroker or his Agent Under Rule 9</b><br/>
            I certify that the above is a true copy of the account maintained under clause (a) of sub-section (1) of section 10 of the Tamil Nadu Pawnbrokers Act, 1943 (Tamil Nadu Act XXIII of 1943), for the loan of Rs.......... taken by .........on...........(date) and that there are no alterations or erasures in the account (except the following).<br/>
            <br/>
            Signature of pawnbroker or his agent.
            """
# Define the content for each form with placeholders
# form_d4_content = """
# <b>Form D-4 [See section 8(7) and rule 6(1)]</b><br/>
# <b>Declaration by Person Claiming to Be Owners of pledge</b><br/>
# I, {name} of {address} in pursuance of sub-section (7) of section 8 of the Tamil Nadu Pawnbrokers Act, 1943 (Tamil Nadu Act XXIII of 1943), do solemnly and sincerely declare that I am the owner of the article/articles described below, pawned at shop of {pawnbroker} pawnbroker and that the pledge in respect of the article/articles was pawned without my knowledge or authority.<br/>
# <br/>
# The article/articles above referred to is/are of the following description:<br/>
# 1. {article1}<br/>
# 2. {article2}<br/>
# <br/>
# Signature of person.<br/>
# Designation.<br/>
# Address.<br/>
# Date.<br/>
# <br/>
# I, {identifier_name} of {identifier_address} in pursuance of sub-section (7) of section 8 of the Act, do solemnly and sincerely declare that I know the person making the foregoing declaration to be {declarant_name} of {declarant_address}.<br/>
# <br/>
# Signature of identifying person.<br/>
# Designation.<br/>
# Address.<br/>
# Date.
# # Define the variables
# variables = {
#     "name": "John Doe",
#     "address": "123 Main St",
#     "pawnbroker": "ABC Pawn Shop",
#     "article1": "Gold Ring",
#     "article2": "Silver Necklace",
#     "identifier_name": "Jane Smith",
#     "identifier_address": "456 Elm St",
#     "declarant_name": "John Doe",
#     "declarant_address": "123 Main St"
# }

# # Format the content with the variables
# formatted_content = form_d4_content.format(**variables)

# # Generate the PDF with the formatted content
# generate_pdf(formatted_content, "form_d4.pdf")
# Generate PDFs for each form
# generate_pdf(form_d4_content, "form_d4.pdf")
# generate_pdf(form_d5_content, "form_d5.pdf")
# generate_pdf(form_d6_content, "form_d6.pdf")
# generate_pdf(form_d7_content, "form_d7.pdf")
# generate_pdf(form_d8_content, "form_d8.pdf")
# generate_pdf(form_g_content, "form_g.pdf")
# generate_pdf(form_h_content, "form_h.pdf")
# generate_pdf(form_i_content, "form_i.pdf")


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
