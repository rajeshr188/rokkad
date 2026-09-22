"""Build a synthetic frame-position review, without a database or production media.

This is a geometry aid, not renderer output or an activatable template pack.
It deliberately reports remaining layout-contract failures instead of inserting
unreviewed business identity or terms into the client's design to make validation pass.
"""

import html
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.tenant_apps.loans.documents import DocumentLayoutValidator, LayoutValidationError, built_in_print_profile, starter_layout


def build_review():
    inventory = json.loads((ROOT / "docs/implementation/fixtures/ticket-template-frame-inventory-20260922.json").read_text(encoding="utf-8"))
    candidates = []
    for template in inventory["templates"]:
        definition = starter_layout("loan_ticket", schema_version=4, layout_mode="ABSOLUTE_OVERLAY").canonical_dict()
        definition.update(name=f"{template['workspace'].upper()} frame mapping - REVIEW ONLY", page_size="A5", blocks=[])
        definition["theme"]["font_family"] = "HELVETICA"
        adjustments = []
        for frame in template["frames"]:
            source, rect = frame["legacy"], frame["candidate_outer_mm"]
            kind = "qr" if source["frame_name"] == "loan_qr" else "image" if source["field_type"] == "image" else "field"
            block = {"type": kind, "binding": frame["candidate_binding"],
                     "copy_scope": {"B": "BOTH", "O": "ORIGINAL", "D": "DUPLICATE"}[source["template_type"]],
                     **{f"{key}_mm": float(value) for key, value in rect.items()},
                     "font_size_pt": int(source["font_size"]), "align": "LEFT"}
            if kind == "field":
                block.update(show_label=False, padding_pt=6, leading_pt=12)
                if block["binding"] in {"collateral.description_lines", "loan.summary_label"}:
                    block.update(overflow_policy="SHRINK", leading_pt=0, max_characters=500)
                    adjustments.append({"frame_id": source["id"], "status": "OWNER_REQUESTED",
                                        "reason": "Wrap collateral text and reduce font/line spacing to fit the existing frame; no continuation sheets."})
            # Owner's reviewed design correction, separate from the source inventory.
            if template["workspace"] == "jcl" and block["binding"] == "borrower.photo":
                adjustments.append({"frame_id": source["id"], "property": "y_mm", "source": block["y_mm"],
                                    "candidate": 50, "status": "OWNER_REQUESTED",
                                    "reason": "Align with customer contact and loan number; clear the collateral description."})
                block["y_mm"] = 50
            if block["x_mm"] + block["width_mm"] > 148:
                adjustments.append({"frame_id": source["id"], "property": "width_mm", "source": block["width_mm"],
                                    "candidate": 148 - block["x_mm"], "status": "REQUIRES_VISUAL_REVIEW"})
                block["width_mm"] = 148 - block["x_mm"]
            definition["blocks"].append(block)
        stamp = {"type": "field", "binding": "document.generated_at", "field_label": "Generated",
                 "show_label": True, "font_size_pt": 7, "leading_pt": 9, "padding_pt": 0,
                 "x_mm": 10, "y_mm": 195, "width_mm": 128, "height_mm": 8, "copy_scope": "BOTH"}
        if template["workspace"] == "jsk":
            definition["blocks"].extend([{**stamp, "copy_scope": "ORIGINAL"},
                {**stamp, "copy_scope": "DUPLICATE", "x_mm": 92, "y_mm": 185, "width_mm": 46, "height_mm": 18}])
        else:
            definition["blocks"].append(stamp)
        if template["workspace"] == "jcl":
            definition["blocks"].extend([
                {"type": "field", "binding": "license.business_name", "show_label": False,
                 "copy_scope": "BOTH", "x_mm": 40, "y_mm": 25, "width_mm": 98, "height_mm": 8,
                 "font_size_pt": 16, "leading_pt": 18, "padding_pt": 0, "align": "CENTER"},
                {"type": "title", "text": "Pawn Brokers", "copy_scope": "BOTH",
                 "x_mm": 40, "y_mm": 33, "width_mm": 98, "height_mm": 5,
                 "font_size_pt": 11, "leading_pt": 12, "padding_pt": 0, "align": "CENTER"},
                {"type": "field", "binding": "license.business_address", "show_label": False,
                 "copy_scope": "BOTH", "x_mm": 40, "y_mm": 38.5, "width_mm": 98, "height_mm": 11,
                 "font_size_pt": 9, "leading_pt": 10, "padding_pt": 0, "align": "CENTER"},
                {"type": "field", "binding": "loan.tenure", "show_label": False,
                 "copy_scope": "BOTH", "x_mm": 64.7, "y_mm": 147.4, "width_mm": 55, "height_mm": 4.2,
                 "font_size_pt": 11, "leading_pt": 11, "padding_pt": 0, "align": "LEFT"},
            ])
            adjustments.append({"bindings": ["license.business_name", "license.business_address"],
                                "status": "OWNER_REQUESTED",
                                "reason": "Print business name alone, Pawn Brokers on its own line, then the licence address/contact block above the borrower row."})
            adjustments.append({"binding": "loan.tenure", "status": "OWNER_REQUESTED",
                                "reason": "Replace both supplied backgrounds' fixed three-month text with approved tenure. Use separately cleaned Original and Duplicate artwork."})
            definition["require_interest_rate"] = False
        adjustments.append({"binding": "document.generated_at", "status": "OWNER_REQUESTED",
                            "reason": "Print the original PDF generation timestamp on both copies; retain it on reprints."})
        parsed_blocks = DocumentLayoutValidator._blocks(definition["blocks"], "loan_ticket", 4, layout_mode="ABSOLUTE_OVERLAY")
        missing = {copy: DocumentLayoutValidator.precision_missing_visible(parsed_blocks, copy, require_interest_rate=definition.get("require_interest_rate", True))
                   for copy in ("ORIGINAL", "DUPLICATE")}
        try:
            DocumentLayoutValidator.load(definition)
        except LayoutValidationError as exc:
            validation_error = str(exc)
        else:
            validation_error = ""
        profile = built_in_print_profile(template["target_profile"]).canonical_dict()
        profile.update(schema_version=2, scaling_policy="ACTUAL_SIZE", stock_mode="PLAIN" if template["workspace"] == "jcl" else "PREPRINTED")
        candidates.append({"workspace": template["workspace"], "ready_to_import": False,
            "layout_candidate": definition, "profile_candidate": profile, "geometry_adjustments": adjustments,
            "validation_error": validation_error, "missing_visible_bindings_under_current_rules": missing,
            "additional_requirements": ["Reviewed business identity/terms and signature areas", "Reviewed artwork and physical calibration"],
            "source_review_flags": [{"frame_id": frame["legacy"]["id"], "flags": frame["review_flags"]} for frame in template["frames"] if frame["review_flags"]]})
    return {"kind": "synthetic_frame_review_not_an_import_pack", "contains_customer_data": False, "templates": candidates}


def build_jsk_calibration_layout():
    """Owner-confirmed stock signatures and movable licence/approved-term fields.

    This is a calibration draft, not proof of alignment with physical stationery.
    It contains bindings only: the business name lives on the selected licence.
    """
    candidate = next(item for item in build_review()["templates"] if item["workspace"] == "jsk")
    definition = candidate["layout_candidate"]
    definition["name"] = "JSK preprinted A5 - calibration draft"
    definition["require_interest_rate"] = False
    for block in definition["blocks"]:
        if block["type"] == "field" and block["binding"] in {"loan.number", "loan.date"}:
            block["overflow_policy"] = "SHRINK"
        if block["type"] == "field" and block["binding"] == "loan.number":
            block["font_size_pt"] = 9
        # The square sample photos expose collisions in the source rectangles.
        # Keep source geometry in the inventory; these are explicit draft choices.
        if block["binding"] == "collateral.first_approved_photo":
            if block["copy_scope"] == "ORIGINAL":
                block.update(x_mm=68, y_mm=108, width_mm=25, height_mm=25)
            else:
                block["y_mm"] = 106
        if block["copy_scope"] == "ORIGINAL" and block["binding"] == "loan.principal":
            block.update(width_mm=30, font_size_pt=10)
        if block["copy_scope"] == "DUPLICATE" and block["binding"] == "collateral.description_lines":
            block["width_mm"] = 75
        if block["copy_scope"] == "ORIGINAL" and block["binding"] == "borrower.photo":
            block["y_mm"] = 64
        if block["copy_scope"] == "DUPLICATE" and block["binding"] == "borrower.contact_block":
            block["width_mm"] = 60
    definition["signature_areas"] = {
        copy: {"source": "PREPRINTED", "asset_key": "", "sha256": ""}
        for copy in ("ORIGINAL", "DUPLICATE")
    }
    def field(binding, x, y, width, height, size, *, scope="BOTH", label="", leading=None):
        return {"type": "field", "binding": binding, "copy_scope": scope,
                "x_mm": x, "y_mm": y, "width_mm": width, "height_mm": height,
                "font_size_pt": size, "leading_pt": leading or size + 1,
                "padding_pt": 0, "show_label": bool(label), "field_label": label}
    definition["blocks"].extend([
        field("license.business_name", 10, 5, 120, 8, 14),
        field("license.number", 10, 14, 85, 5, 9, label="Licence"),
        field("license.business_address", 10, 20, 85, 10, 8),
    ])
    for scope, y in (("ORIGINAL", 162), ("DUPLICATE", 150)):
        definition["blocks"].extend([
            field("loan.tenure", 82, y, 56, 6, 9, scope=scope, label="Tenure"),
        ])
    return DocumentLayoutValidator.load(definition).canonical_dict()


def review_html(review):
    sample = {"document.generated_at": "22-09-2026 20:05:30 IST (UTC+05:30)", "license.number": "TEST-LIC", "borrower.contact_block": "TEST Customer\nS/o TEST Parent\n10 Test Road\n9000000000",
              "license.business_name": "JCL (Sample)", "license.business_address": "10 Sample Business Road\nVellore, Tamil Nadu\nPhone: 9000000001",
              "loan.tenure": "6 months",
              "loan.number": "TEST-19", "loan.date": "22-09-2026", "collateral.description_lines": "1. Test ring",
              "collateral.net_weight_by_metal": "Gold: 2 g", "collateral.approved_appraisal_total": "12000.00",
              "loan.principal": "10000.00", "loan.principal_words": "Ten thousand rupees only",
              "loan.summary_label": "TEST-19 / 22-09-2026\nRs 10000 / Gold: 2 g\nTEST Customer\n1. Test ring"}
    parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><title>JCL / JSK frame-position review</title>',
             '<style>body{font:16px system-ui;background:#edf1f5;color:#17232d;padding:24px}h1{margin-top:0}.note{max-width:1000px;line-height:1.6}.copies{display:flex;gap:12px;flex-wrap:wrap}.sheet{width:148mm;height:210mm;position:relative;background:white;border:1px solid #788996;margin:12px 0}.frame{position:absolute;box-sizing:border-box;outline:1px dashed #b1bfcb;white-space:pre-wrap;overflow:visible;font:12pt/12pt Helvetica,Arial,sans-serif}.frame small{position:absolute;top:-10px;left:0;color:#536b7e;font:8px system-ui;white-space:nowrap}.media{display:grid;place-items:center;background:repeating-linear-gradient(45deg,#e4ebf1,#e4ebf1 4px,#f4f7fa 4px,#f4f7fa 8px);font:10px system-ui;color:#405c70}.copy-name{font-weight:700}pre{white-space:pre-wrap;max-width:1000px}summary{cursor:pointer}#guides:not(:checked)~main small{display:none}#guides:not(:checked)~main .frame{outline:none}@media print{body{background:white;padding:0}.note,details,label,input{display:none}.sheet{break-inside:avoid}.sheet:after{content:"GEOMETRY REVIEW ONLY - NOT A LOAN TICKET";position:absolute;bottom:5mm;left:8mm;color:#b00020;font-size:10px}}</style>',
             '<h1>JCL / JSK frame-position review</h1><p class="note"><strong>Synthetic geometry aid, not an issued ticket or renderer preview.</strong> No production artwork is included. All 35 source frames are mapped, with an added generation timestamp on each copy. Text wrapping here is browser approximation; ReportLab preview and physical printer checks are still required. The original rectangles can overlap and longer content may not fit. These candidates cannot yet be imported: business identity/terms and signature areas still need visible frames or reviewed stationery. Internal audit IDs and verification strings no longer have to print.</p><input id="guides" type="checkbox" checked><label for="guides"> Show frame boundaries and binding names</label><main>']
    for candidate in review["templates"]:
        parts.append(f'<h2>{candidate["workspace"].upper()} — {candidate["profile_candidate"]["composition"]}</h2><div class="copies">')
        for copy in ("ORIGINAL", "DUPLICATE"):
            parts.append(f'<div><div class="copy-name">{copy}</div><div class="sheet">')
            for block in candidate["layout_candidate"]["blocks"]:
                if block["copy_scope"] not in ("BOTH", copy):
                    continue
                is_media = block["type"] in ("image", "qr")
                style = f'left:{block["x_mm"]}mm;top:{block["y_mm"]}mm;width:{block["width_mm"]}mm;height:{block["height_mm"]}mm;padding:{block.get("padding_pt", 0)}pt;font-size:{block["font_size_pt"]}pt;line-height:{block.get("leading_pt", 12)}pt'
                value = ("QR position" if block["type"] == "qr" else "Photo position") if is_media else block.get("text") or sample[block["binding"]]
                if not is_media and block.get("show_label"):
                    value = f"{block['field_label']}: {value}"
                parts.append(f'<div class="frame {"media" if is_media else ""}" style="{style}"><small>{html.escape(block.get("binding", "Text"))}</small>{html.escape(value)}</div>')
            parts.append('</div></div>')
        details = {key: value for key, value in candidate.items() if key not in {"layout_candidate", "profile_candidate"}}
        parts.append(f'</div><details><summary>Validation and unresolved source differences</summary><pre>{html.escape(json.dumps(details, indent=2))}</pre></details>')
    return "\n".join(parts) + '</main></html>'


if __name__ == "__main__":
    output = ROOT / "outputs/ticket-template-tests/frame-review"
    output.mkdir(parents=True, exist_ok=True)
    review = build_review()
    (output / "candidates.json").write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")
    (output / "index.html").write_text(review_html(review), encoding="utf-8")
    print(output / "index.html")
    for candidate in review["templates"]:
        print(candidate["workspace"], len(candidate["layout_candidate"]["blocks"]), candidate["validation_error"])
