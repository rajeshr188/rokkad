"""Application service for Girvi ticket printing workflows."""

from dataclasses import dataclass

from apps.tenant_apps.girvi.documents.loan_ticket import build_loan_ticket_pdf
from apps.tenant_apps.girvi.models.template import LoanTemplate


@dataclass
class LoanPrintResult:
    template: object = None
    pdf: bytes | None = None
    readiness: dict | None = None
    error_message: str = ""

    @property
    def ok(self):
        return self.template is not None and self.pdf is not None


class LoanPrintService:
    """Resolve templates, assess readiness, and render loan ticket PDFs."""

    ASSET_EXPECTATIONS = {
        "O": [
            ("base_template", "Base PDF", "Printing will use a blank front page until one is uploaded."),
        ],
        "OT": [
            ("base_template", "Base PDF", "Printing will use a blank front page until one is uploaded."),
            ("terms_template", "Terms PDF", "The back page will be omitted until it is uploaded."),
        ],
        "D": [
            ("dup_template", "Duplicate PDF", "Duplicate printing will use a blank page until one is uploaded."),
        ],
        "DF": [
            ("dup_template", "Duplicate PDF", "Duplicate printing will use a blank page until one is uploaded."),
            ("form_d3_template", "Form D3 PDF", "The back page will be omitted until it is uploaded."),
        ],
        "BS": [
            ("base_template", "Base PDF", "Original copy will use a blank page until one is uploaded."),
            ("dup_template", "Duplicate PDF", "Duplicate copy will use a blank page until one is uploaded."),
        ],
        "BD": [
            ("base_template", "Base PDF", "Original front page will use a blank page until one is uploaded."),
            ("dup_template", "Duplicate PDF", "Duplicate front page will use a blank page until one is uploaded."),
            ("terms_template", "Terms PDF", "Original back page will be omitted until it is uploaded."),
            ("form_d3_template", "Form D3 PDF", "Duplicate back page will be omitted until it is uploaded."),
        ],
        "BA": [
            ("base_template", "Base PDF", "Original side will use a blank page until one is uploaded."),
            ("dup_template", "Duplicate PDF", "Duplicate side will use a blank page until one is uploaded."),
        ],
        "BDA": [
            ("base_template", "Base PDF", "Original front side will use a blank page until one is uploaded."),
            ("dup_template", "Duplicate PDF", "Duplicate front side will use a blank page until one is uploaded."),
            ("terms_template", "Terms PDF", "Original back side will be omitted until it is uploaded."),
            ("form_d3_template", "Form D3 PDF", "Duplicate back side will be omitted until it is uploaded."),
        ],
    }

    RECOMMENDED_FRAME_LABELS = {
        "loan_id": "Loan ID",
        "loan_date": "Date",
        "customer_info": "Customer Info",
        "loan_desc": "Loan Description",
        "amount": "Amount",
        "amount_words": "Amount in Words",
        "loan_qr": "Loan QR Code",
    }

    @staticmethod
    def get_active_default_template():
        return LoanTemplate.objects.filter(is_default=True, is_active=True).first()

    @staticmethod
    def _has_file(file_field):
        return bool(file_field and getattr(file_field, "name", None))

    @classmethod
    def _configured_frame_names(cls, template):
        frame_manager = getattr(template, "templateframe_set", None)
        if not frame_manager or not hasattr(frame_manager, "all"):
            return []
        return sorted(
            {
                getattr(frame, "frame_name", None)
                for frame in frame_manager.all()
                if getattr(frame, "frame_name", None)
            }
        )

    @classmethod
    def assess_template_readiness(cls, template):
        if not template:
            return {
                "is_ready": False,
                "can_set_default": False,
                "status_label": "Missing template",
                "status_class": "danger",
                "summary": "No template selected.",
                "blocking_issues": ["No template selected."],
                "warnings": [],
                "configured_frame_count": 0,
                "missing_recommended_frames": [],
            }

        blocking_issues = []
        warnings = []

        if not getattr(template, "is_active", False):
            blocking_issues.append(
                "Template is inactive. Activate it before marking it as default."
            )

        try:
            page_width = float(getattr(template, "page_width", 0) or 0)
            page_height = float(getattr(template, "page_height", 0) or 0)
        except (TypeError, ValueError):
            page_width = 0
            page_height = 0

        if page_width <= 0 or page_height <= 0:
            blocking_issues.append(
                "Page dimensions are invalid. Set a positive page width and height."
            )

        configured_frame_names = cls._configured_frame_names(template)
        if not configured_frame_names:
            blocking_issues.append("No frames configured yet.")

        missing_recommended_frames = [
            label
            for frame_name, label in cls.RECOMMENDED_FRAME_LABELS.items()
            if frame_name not in configured_frame_names
        ]
        if missing_recommended_frames:
            warnings.append(
                "Recommended starter frames still missing: "
                + ", ".join(missing_recommended_frames)
                + "."
            )

        for field_name, label, consequence in cls.ASSET_EXPECTATIONS.get(
            getattr(template, "print_option", None), []
        ):
            if not cls._has_file(getattr(template, field_name, None)):
                warnings.append(f"{label} is missing. {consequence}")

        is_ready = not blocking_issues
        if blocking_issues:
            status_label = "Needs attention"
            status_class = "danger"
            summary = "; ".join(blocking_issues)
        elif warnings:
            status_label = "Ready with warnings"
            status_class = "warning"
            summary = warnings[0] if len(warnings) == 1 else f"{warnings[0]} (+{len(warnings) - 1} more warning(s))"
        else:
            status_label = "Ready"
            status_class = "success"
            summary = "Template is ready for printing."

        return {
            "is_ready": is_ready,
            "can_set_default": is_ready,
            "status_label": status_label,
            "status_class": status_class,
            "summary": summary,
            "blocking_issues": blocking_issues,
            "warnings": warnings,
            "configured_frame_count": len(configured_frame_names),
            "missing_recommended_frames": missing_recommended_frames,
        }

    @staticmethod
    def format_readiness_summary(readiness_report):
        if not readiness_report:
            return ""
        if readiness_report.get("blocking_issues"):
            return "; ".join(readiness_report["blocking_issues"])
        if readiness_report.get("warnings"):
            return " ".join(readiness_report["warnings"][:2])
        return readiness_report.get("summary", "")

    @classmethod
    def resolve_template(cls, template=None, template_resolver=None):
        if template is not None:
            return template
        if template_resolver is not None:
            return template_resolver()
        return cls.get_active_default_template()

    @staticmethod
    def render_pdf(loan, template, renderer=None):
        active_renderer = renderer or build_loan_ticket_pdf
        return active_renderer(loan=loan, template_id=template.pk)

    @classmethod
    def build_print_result(cls, loan, template=None, template_resolver=None, renderer=None):
        active_template = cls.resolve_template(
            template=template,
            template_resolver=template_resolver,
        )
        if not active_template:
            readiness = cls.assess_template_readiness(None)
            return LoanPrintResult(
                template=None,
                pdf=None,
                readiness=readiness,
                error_message="No default template configured. Please set a default template.",
            )

        readiness = cls.assess_template_readiness(active_template)
        pdf = cls.render_pdf(loan, active_template, renderer=renderer)
        if pdf is None:
            error_detail = (
                cls.format_readiness_summary(readiness)
                if readiness.get("blocking_issues") or readiness.get("warnings")
                else "Review the template setup and server logs for the failing frame."
            )
            return LoanPrintResult(
                template=active_template,
                pdf=None,
                readiness=readiness,
                error_message=(
                    f'Failed to generate loan PDF using template "{getattr(active_template, "name", "selected template")}". '
                    f"{error_detail}"
                ),
            )

        return LoanPrintResult(
            template=active_template,
            pdf=pdf,
            readiness=readiness,
            error_message="",
        )

    @classmethod
    def render_loan_ticket(cls, loan, template=None, template_resolver=None, renderer=None):
        active_template = cls.resolve_template(
            template=template,
            template_resolver=template_resolver,
        )
        if not active_template:
            return None, None
        pdf = cls.render_pdf(loan, active_template, renderer=renderer)
        return active_template, pdf
