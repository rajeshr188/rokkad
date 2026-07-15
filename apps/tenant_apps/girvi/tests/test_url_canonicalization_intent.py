from pathlib import Path

from django.test import SimpleTestCase
from django.urls import resolve, reverse

from apps.tenant_apps.girvi import urls as girvi_urls


class GirviUrlCanonicalizationIntentTests(SimpleTestCase):
    def test_canonical_and_alias_reverse_to_same_path(self):
        route_cases = {
            "loan_list_report": ({},),
            "loan_transition": ({"pk": 7},),
            "statement_list": ({},),
            "statement_create": ({},),
            "statement_update": ({"pk": 7},),
            "storage_boxes_list": ({},),
            "storage_boxes_add": ({},),
            "storage_boxes_update": ({"pk": 7},),
            "storage_boxes_delete": ({"pk": 7},),
        }

        for route_key, (kwargs,) in route_cases.items():
            with self.subTest(route_key=route_key):
                canonical_name = girvi_urls.GIRVI_CANONICAL_ROUTE_NAMES[route_key]
                alias_name = girvi_urls.GIRVI_FROZEN_ALIAS_ROUTE_NAMES[route_key]
                canonical_path = reverse(f"girvi:{canonical_name}", kwargs=kwargs)
                alias_path = reverse(f"girvi:{alias_name}", kwargs=kwargs)
                self.assertEqual(canonical_path, alias_path)

    def test_duplicate_paths_resolve_to_canonical_route_names(self):
        canonical_path_cases = {
            "loan_list_report": reverse("girvi:girvi_loan_list_report"),
            "loan_transition": reverse("girvi:girvi_loan_transition", kwargs={"pk": 7}),
            "statement_list": reverse("girvi:girvi_statement_list"),
            "statement_create": reverse("girvi:girvi_statement_create"),
            "statement_update": reverse("girvi:girvi_statement_update", kwargs={"pk": 7}),
            "storage_boxes_list": reverse("girvi:girvi_storage_boxes"),
            "storage_boxes_add": reverse("girvi:girvi_add_storage_box"),
            "storage_boxes_update": reverse("girvi:girvi_update_storage_box", kwargs={"pk": 7}),
            "storage_boxes_delete": reverse("girvi:girvi_delete_storage_box", kwargs={"pk": 7}),
        }

        for route_key, path in canonical_path_cases.items():
            with self.subTest(route_key=route_key):
                resolved = resolve(path)
                self.assertEqual(
                    resolved.url_name,
                    girvi_urls.GIRVI_CANONICAL_ROUTE_NAMES[route_key],
                )

    def test_internal_runtime_routes_use_canonical_names_not_aliases(self):
        project_root = Path(__file__).resolve().parents[4]
        alias_route_names = set(girvi_urls.GIRVI_FROZEN_ALIAS_ROUTE_NAMES.values())
        include_roots = [
            project_root / "apps" / "tenant_apps" / "girvi",
            project_root / "templates" / "girvi",
        ]
        excluded_suffixes = {
            "apps/tenant_apps/girvi/urls.py",
            "apps/tenant_apps/girvi/tests/test_url_canonicalization_intent.py",
        }

        for root in include_roots:
            for file_path in root.rglob("*"):
                if file_path.suffix not in {".py", ".html"}:
                    continue
                relative_path = file_path.relative_to(project_root).as_posix()
                if relative_path in excluded_suffixes:
                    continue

                content = file_path.read_text(encoding="utf-8-sig")
                for alias_name in alias_route_names:
                    with self.subTest(file=relative_path, alias=alias_name):
                        self.assertNotIn(f"girvi:{alias_name}", content)
