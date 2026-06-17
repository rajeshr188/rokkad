---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Quick Reference: Phase 1 Changes

**Last Updated:** February 28, 2026

---

## View Name Changes - Quick Lookup

### apps/orgs/views.py

| Old Name | New Name | Use For |
|----------|----------|---------|
| `company_create` | `workspace_create` | Creating new workspace |
| `company_list` | `workspace_list` | Listing user's workspaces |
| `company_detail` | `workspace_detail` | Showing workspace details + team |
| `company_update` | `workspace_update` | Editing workspace settings |
| `company_delete` | `workspace_delete` | Deleting workspace |
| `workspace_home` | `workspace_selector` | Selecting which workspace to enter |
| `create_invite` | `team_invite` | Sending team invitation |
| `membership_revoke` | `team_remove_member` | Removing team member |
| `membership_update` | `team_change_role` | Changing member's role |
| `workspace_invitations` | `team_invitations` | Viewing/accepting invitations |

### pages/views.py

| Function | Status | Purpose |
|----------|--------|---------|
| `Dashboard()` | âœ… **UPDATED** | Smart router - redirects to correct destination |
| `company_dashboard()` | âš ï¸ **DEPRECATED** | Now redirects to `workspace_dashboard` |

### NEW in apps/orgs/views.py

| Function | Purpose |
|----------|---------|
| `workspace_dashboard(request, workspace_id)` | Main workspace dashboard with all metrics |

---

## URL Name Changes - Quick Lookup

### Preferred (New)

| What You Want | URL Name | Pattern |
|---------------|----------|---------|
| Select workspace | `workspace_selector` | `/workspace/` |
| Workspace dashboard | `workspace_dashboard` | `/workspace/<id>/dashboard/` |
| Create workspace | `workspace_create` | `/workspace/create/` |
| List workspaces | `workspace_list` | `/workspace/list/` |
| Workspace details | `workspace_detail` | `/workspace/<id>/` |
| Edit workspace | `workspace_update` | `/workspace/<id>/edit/` |
| Delete workspace | `workspace_delete` | `/workspace/<id>/delete/` |
| Invite team member | `team_invite` | `/workspace/<id>/team/invite/` |
| View invitations | `team_invitations` | `/team/invitations/` |
| Accept invitation | `team_accept_invitation` | `/team/invitations/accept/<key>/` |
| Remove member | `team_remove_member` | `/workspace/<id>/team/member/<mid>/remove/` |
| Change role | `team_change_role` | `/workspace/<id>/team/member/<mid>/role/` |

### Legacy (Still Work)

| Old URL Name | Use Instead |
|-------------|-------------|
| `orgs_company_create` | `workspace_create` |
| `orgs_company_list` | `workspace_list` |
| `orgs_company_detail` | `workspace_detail` |
| `orgs_company_update` | `workspace_update` |
| `orgs_company_delete` | `workspace_delete` |
| `invite_to_company` | `team_invite` |
| `orgs_membership_revoke` | `team_remove_member` |
| `orgs_membership_update` | `team_change_role` |
| `workspace_home` | `workspace_selector` |
| `company_dashboard` | `workspace_dashboard` |

---

## Template Usage

### OLD Way (Still Works)
```django
<a href="{% url 'orgs_company_list' %}">My Workspaces</a>
<a href="{% url 'orgs_company_detail' company.id %}">Details</a>
<a href="{% url 'invite_to_company' company.id %}">Invite</a>
<a href="{% url 'company_dashboard' %}">Dashboard</a>
```

### NEW Way (Recommended)
```django
<a href="{% url 'workspace_list' %}">My Workspaces</a>
<a href="{% url 'workspace_detail' workspace.id %}">Details</a>
<a href="{% url 'team_invite' workspace.id %}">Invite</a>
<a href="{% url 'workspace_dashboard' workspace.id %}">Dashboard</a>
```

---

## View Usage

### OLD Way (Still Works)
```python
from apps.orgs.views import company_list, company_detail, create_invite

return redirect('orgs_company_list')
return redirect('company_dashboard')
```

### NEW Way (Recommended)
```python
from apps.orgs.views import workspace_list, workspace_detail, team_invite

return redirect('workspace_list')
return redirect('workspace_dashboard', workspace_id=workspace.id)
```

---

## Common Redirects

| From | To | Code |
|------|----|----- |
| After login | Dashboard router | `redirect('dashboard')` |
| After workspace create | Workspace dashboard | `redirect('workspace_dashboard', workspace_id=workspace.id)` |
| After team invite | Invite success | `redirect('team_invite_success')` |
| After accept invite | Workspace dashboard | `redirect('workspace_dashboard', workspace_id=workspace.id)` |
| No workspace selected | Workspace selector | `redirect('workspace_selector')` |

---

## User Flow Summary

```
User â†’ Login
    â†“
pages.Dashboard() [Smart Router]
    â†“
    â”œâ”€ Has workspace? â†’ workspace_dashboard(workspace_id) âœ…
    â”œâ”€ Has memberships? â†’ workspace_selector âœ…
    â””â”€ No memberships? â†’ workspace_create âœ…
```

**Key Improvement:** Only **1 redirect** instead of 3-4

---

## Testing Commands

```bash
# Activate virtual environment
& .venv\Scripts\Activate.ps1

# Run development server
python manage.py runserver

# Check for errors
python manage.py check

# Test specific view
python manage.py shell
>>> from apps.orgs.views import workspace_dashboard
>>> print(workspace_dashboard.__doc__)
```

---

## Files Changed

- âœ… `apps/orgs/views.py` - Renamed 10 views, added workspace_dashboard
- âœ… `pages/views.py` - Simplified Dashboard, deprecated company_dashboard
- âœ… `apps/orgs/urls.py` - Restructured with new patterns
- âœ… `pages/urls.py` - Import from orgs, simplified patterns

---

## What's Next?

### Phase 2: Search and Replace

Find and replace these in **all templates**:

```bash
# Search for old URL names
grep -r "orgs_company" templates/
grep -r "company_dashboard" templates/
grep -r "invite_to_company" templates/

# Replace with new names
orgs_company_list â†’ workspace_list
orgs_company_detail â†’ workspace_detail
orgs_company_create â†’ workspace_create
company_dashboard â†’ workspace_dashboard
invite_to_company â†’ team_invite
```

---

**Need Help?**
- See [PHASE_1_COMPLETE.md](PHASE_1_COMPLETE.md) for full details
- See [ARCHITECTURE_ASSESSMENT_AND_RECOMMENDATION.md](ARCHITECTURE_ASSESSMENT_AND_RECOMMENDATION.md) for overall plan

