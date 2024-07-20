def create_label_pdf(
    file_name, loan_id, date, amount, weight, customer, item_description
):
    label_content = [
        f"Loan ID: {loan_id}",
        f"Date: {date}",
        f"Amount: {amount}",
        f"Weight: {weight}",
        f"Customer: {customer}",
        f"Item Description: {item_description}",
    ]

    width, height = 4 * 72, 2 * 72  # 4 inches * 72 points, 2 inches * 72 points
    c = canvas.Canvas(file_name, pagesize=(width, height))

    # Set initial y-coordinate
    y = height - 20  # Start 20 points from the top of the page

    # Write each line of label content
    for line in label_content:
        c.drawString(10, y, line)
        y -= 15  # Decrement y-coordinate for next line

    c.showPage()
    c.save()
