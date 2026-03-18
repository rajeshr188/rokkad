#!/usr/bin/env python3
"""
Phase 2: Complete URL Standardization in all templates
This script updates all old Django URL names to new standardized names.
"""
import os
import sys

# Mapping of old URL names to new ones (without quotes)
url_mappings = [
    ("orgs_company_list", "workspace_list"),
    ("orgs_company_detail", "workspace_detail"),
    ("orgs_company_create", "workspace_create"),
    ("orgs_company_update", "workspace_update"),
    ("orgs_company_delete", "workspace_delete"),
    ("company_dashboard", "workspace_dashboard"),
    ("invite_to_company", "team_invite"),
    ("orgs_membership_update", "team_change_role"),
    ("orgs_membership_revoke", "team_remove_member"),
    ("workspace_home", "workspace_selector"),
]


def update_templates():
    """Update all HTML templates with new URL names"""
    templates_dir = "templates"
    files_updated = 0
    total_replacements = 0

    for root, dirs, files in os.walk(templates_dir):
        for file in files:
            if not file.endswith(".html"):
                continue

            filepath = os.path.join(root, file)

            try:
                with open(filepath, "r", encoding="utf-8", newline="") as f:
                    content = f.read()

                original_content = content
                replacements_count = 0

                # Replace each URL mapping
                for old_url, new_url in url_mappings:
                    # Handle both single and double quote variants
                    for quote in ["'", '"']:
                        old_pattern = f"{quote}{old_url}{quote}"
                        new_pattern = f"{quote}{new_url}{quote}"

                        while old_pattern in content:
                            content = content.replace(old_pattern, new_pattern, 1)
                            replacements_count += 1

                # Write back if changed
                if content != original_content:
                    with open(filepath, "w", encoding="utf-8", newline="") as f:
                        f.write(content)
                    files_updated += 1
                    total_replacements += replacements_count
                    print(f"✓ {filepath} ({replacements_count} replacements)")

            except Exception as e:
                print(f"✗ Error updating {filepath}: {str(e)}", file=sys.stderr)

    print(f"\n{'='*70}")
    print(f"Phase 2 Template Update Summary:")
    print(f"  Files updated: {files_updated}")
    print(f"  Total replacements: {total_replacements}")
    print(f"{'='*70}")

    return files_updated, total_replacements


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)) or ".")
    files_updated, total_replacements = update_templates()
    sys.exit(0 if files_updated > 0 else 1)
