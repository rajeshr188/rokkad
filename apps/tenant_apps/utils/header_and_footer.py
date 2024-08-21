class PageNumCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self.pages = []

    def showPage(self):
        self.pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        page_count = len(self.pages)
        for page in self.pages:
            self.__dict__.update(page)
            self.draw_header_footer(page_count)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_header_footer(self, page_count):
        self.setFont("Helvetica", 10)
        self.drawRightString(200 * mm, 20 * mm, "Page %d of %d" % (self._pageNumber, page_count))

        # Draw header
        self.saveState()
        styles = getSampleStyleSheet()
        header = Paragraph("Loan Report", styles['Heading1'])
        w, h = header.wrap(self._pagesize[0] - 2 * inch, self._pagesize[1])
        header.drawOn(self, inch, self._pagesize[1] - inch - h)
        self.restoreState()