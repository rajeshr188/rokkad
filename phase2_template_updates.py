#!/usr/bin/env python
"""
Phase 2: URL Standardization - Update all template URL names
"""
import os

# URL replacements mapping
replacements = {
    "'orgs_company_list'": "'workspace_list'",
    "'orgs_company_detail'": "'workspace_detail'",
    "'orgs_company_create'": "'workspace_create'",
    "'company_dashboard'": "'workspace_dashboard'",
    "'invite_to_company'": "'team_invite'",
    "'orgs_membership_update'": "'team_change_role'",
    "'orgs_membership_revoke'": "'team_remove_member'",
    "'workspace_home'": "'workspace_selector'",
}

template_dir = "templates"
files_modified = 0
total_replacements = 0

for root, dirs, files in os.walk(template_dir):
    for file in files:
        if file.endswith(".html"):
            filepath = os.path.join(root, file)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                original = content
                replacements_in_file = 0

                for old, new in replacements.items():
                    count_before = content.count(old)
                    content = content.replace(old, new)
                    count_after = content.count(new)
                    if count_before > 0:
                        replacements_in_file += count_before

                if content != original:
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(content)
                    files_modified += 1
                    total_replacements += replacements_in_file
                    print(f"✓ {filepath} - {replacements_in_file} replacements")

            except Exception as e:
                print(f"✗ Error processing {filepath}: {e}")

output = f"\n" + "=" * 70 + "\n"
output += f"Phase 2 Summary:\n"
output += f"  Files modified: {files_modified}\n"
output += f"  Total replacements: {total_replacements}\n"
output += "=" * 70

print(output)

# Also write to file
with open("phase2_results.txt", "w") as f:
    f.write(output)
