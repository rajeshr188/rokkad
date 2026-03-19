# Quick Testing Guide - Navigation & UI Improvements

## 🎯 What Was Changed

All gaps from the IMPLEMENTATION_ANALYSIS_AND_GAPS.md have been addressed:

| Gap | Solution | Status |
|-----|----------|--------|
| Workspace admin actions missing | Added subscription widget + 3 admin action cards | ✅ |
| Navigation config system | Verified existing system in django_project/navigation.py | ✅ |
| Breadcrumb consistency | Enhanced component with multi-format support | ✅ |
| Active link highlighting | Added to all 11+ navigation items | ✅ |
| Mobile responsiveness | Added offcanvas sidebar with toggle button | ✅ |
| Permission-based navigation | Verified working with context processors | ✅ |
| Tenant app integration | Verified in sidebar with permission checks | ✅ |
| Subscription status display | Added to sidebar + dashboard widget | ✅ |

---

## 🧪 Quick Test Scenarios

### Test 1: Permission-Based Navigation (5 min)
**What to test:** Sidebar sections appear/disappear based on user permissions

**Steps:**
1. Create test user with "Member" role
2. Login and go to Dashboard
3. **Expected:** Only see "Dashboard" in sidebar (no Team, Billing, Settings sections)
4. Create user with "Admin" role
5. Login and reload page
6. **Expected:** See Dashboard + Team + Workspace + Billing sections

**Key Files to Check:**
- [templates/components/navigation/sidebar.html](templates/components/navigation/sidebar.html#L28-L75)

---

### Test 2: Workspace Admin Actions (3 min)
**What to test:** Dashboard shows admin control cards

**Steps:**
1. Login as Workspace Owner/Admin
2. Go to workspace dashboard
3. **Expected:** See "Subscription Status" widget (4-6 rows below page header)
4. **Expected:** See "Admin Actions" section with 3 cards:
   - Invite Team Member
   - Manage Members
   - Settings

**Try This:**
- Click each card button and verify navigation
- Check if subscription status shows correctly (green if active, orange if renewal needed)
- Hover over action cards - should lift slightly

**Key Files:**
- [templates/company/workspace_dashboard.html](templates/company/workspace_dashboard.html#L28-L77)

---

### Test 3: Mobile Navigation (5 min)
**What to test:** Sidebar works on mobile devices

**Steps:**
1. Open browser dev tools (F12)
2. Toggle device toolbar (Ctrl+Shift+M)
3. Select mobile device (iPhone 14, Pixel 7, etc.)
4. Navigate to workspace dashboard
5. **Expected:** Sidebar NOT visible
6. **Expected:** Blue button with 3 lines icon (☰) in bottom-right corner
7. Click the button
8. **Expected:** Sidebar slides in from left side
9. Click a navigation item
10. **Expected:** Sidebar closes automatically, content updates

**Size to Test:**
- Mobile (< 992px): Toggle button + offcanvas sidebar
- Desktop (≥ 992px): Sidebar always visible

**Key Files:**
- [templates/layouts/workspace.html](templates/layouts/workspace.html#L12-L50)

---

### Test 4: Active Link Highlighting (3 min)
**What to test:** Current page highlighted in sidebar

**Steps:**
1. Login and go to Dashboard
2. **Expected:** "Dashboard" link has blue background
3. Click "Members" link (in Team section)
4. **Expected:** "Members" link now highlighted, Dashboard is not
5. Click a feature link (e.g., "Girvi (Loans)")
6. **Expected:** "Girvi" link highlighted
7. Navigate between different features
8. **Expected:** Highlighting follows your current location

**Features to Click:**
- Contacts
- Girvi (if permission has girvi_loan_view)
- Sales (if permission has sales_invoice_view)
- Purchase (if permission has purchase_invoice_view)
- Accounting (if permission has dea_journal_view)

**Key Files:**
- [templates/components/navigation/sidebar.html](templates/components/navigation/sidebar.html)
  - Dashboard: line 23
  - Members: line 32
  - Settings: line 54
  - Girvi: line 85
  - etc.

---

### Test 5: Breadcrumb Navigation (3 min)
**What to test:** Breadcrumb trail shows current location

**Steps:**
1. Go to workspace dashboard
2. **Expected:** Breadcrumb shows: "Home > Workspace Name > Dashboard"
3. Click settings link
4. **Expected:** Breadcrumb updates: "Home > Workspace Name > Settings"
5. Verify breadcrumb links work (click "Home" should go to dashboard selector)

**Example Breadcrumbs:**
- Dashboard view: Home > Workspace Name > Dashboard
- Settings view: Home > Workspace Name > Settings
- Feature view: Home > Workspace Name > Girvi (Loans)

**Key Files:**
- [templates/components/navigation/breadcrumbs.html](templates/components/navigation/breadcrumbs.html)

---

### Test 6: Subscription Status (3 min)
**What to test:** Subscription display in sidebar and dashboard

**Steps:**
1. Login as workspace owner
2. Look at sidebar bottom (Workspace Stats section)
3. **Expected:** See "Subscription:" label with status badge
4. **If Active:** Green badge with plan name + renewal countdown
5. **If Inactive:** Orange badge "Renewal Needed"
6. Go to workspace dashboard
7. **Expected:** See "Subscription Status" widget below Workspace Stats
8. Click "Manage Subscription" button
9. **Expected:** Navigate to subscriptions app

**Key Files:**
- Sidebar status: [sidebar.html#L174-L185](templates/components/navigation/sidebar.html#L174-L185)
- Dashboard widget: [workspace_dashboard.html#L28-L65](templates/company/workspace_dashboard.html#L28-L65)

---

## 📊 Testing Matrix

| Feature | Desktop | Tablet | Mobile | Expected |
|---------|---------|--------|--------|----------|
| Sidebar visible | ✅ | ✅ | ❌ | Visible on lg+ only |
| Toggle button | ❌ | ❌ | ✅ | Visible on mobile only |
| Nav links active | ✅ | ✅ | ✅ | Always highlighted |
| Breadcrumbs | ✅ | ✅ | ✅ | Always visible |
| Subscription status | ✅ | ✅ | ✅ | In sidebar footer |
| Admin actions | ✅ | ✅ | ✅ | On dashboard grid |

---

## 🔍 Debug Checklist

If something doesn't work, check:

### Navigation Not Showing
- [ ] Are you authenticated? (Check if logout link visible)
- [ ] Is sidebar block in template? (Check [workspace.html](templates/layouts/workspace.html#L16-L20))
- [ ] Are context processors registered? (Check [settings/base.py#L147-L150](django_project/settings/base.py#L147-L150))
- [ ] Check browser console for JS errors (F12 > Console)

### Permissions Not Working
- [ ] Check user's membership role
- [ ] Verify role has required permission (check [django_project/context_processors.py#L66-L94](django_project/context_processors.py#L66-L94))
- [ ] Clear browser cache (Ctrl+Shift+Delete)
- [ ] Check that user_permissions is set in request (add to template: `{{ user_permissions }}`)

### Mobile Navigation Not Working
- [ ] Check Bootstrap 5 is loaded (check source, should see bootstrap.bundle.js)
- [ ] Verify offcanvas CSS is present
- [ ] Check that JavaScript is enabled
- [ ] Open dev tools (F12) Console tab - any errors?
- [ ] Try different mobile viewport sizes

### Links Not Highlighted
- [ ] Check `request.resolver_match` exists (add to template: `{{ request.resolver_match.url_name }}`)
- [ ] Verify URL name matches nav link URL name
- [ ] For namespaced URLs, check namespace matches (e.g., 'girvi' for girvi:girvi_loan_list)
- [ ] Check active CSS exists in sidebar (look for `.nav-link.active { background-color: #0d6efd; }`)

### Subscription Widget Not Showing
- [ ] Check permission exists: 'billing_view' in user_permissions
- [ ] Check subscription object exists in database
- [ ] Verify context processor returning subscription_context (add to template: `{{ has_active_subscription }}`)

---

## 🚀 Quick Start Test (10 min)

### Fastest Way to Verify Everything Works:

1. **Open Django Shell:**
   ```bash
   python manage.py shell
   ```

2. **Check Permissions Are Available:**
   ```python
   from apps.orgs.models import Role
   admin_role = Role.objects.get(name='Admin')
   print(admin_role.permissions.all())  # Should show many permissions
   ```

3. **Test in Browser:**
   - Login as Admin user
   - Go to workspace dashboard (e.g., `/workspace/1/dashboard/`)
   - ✅ Should see sidebar with multiple sections
   - ✅ Should see subscription status widget
   - ✅ Should see admin action cards
   - ✅ Mobile toggle button appears on small screens

4. **Verify Mobile:**
   - Press F12, then Ctrl+Shift+M
   - Select mobile device
   - Resize to < 992px
   - ✅ Sidebar should HIDE
   - ✅ Toggle button should APPEAR
   - ✅ Click button to see offcanvas sidebar

---

## 📝 Reporting Issues

If tests fail, please provide:

1. **Browser/Device:**
   - [ ] Device type (desktop/tablet/mobile)
   - [ ] Browser (Chrome/Firefox/Safari)
   - [ ] Browser version

2. **User Role:**
   - [ ] Owner / Admin / Member

3. **Permission Set:**
   - [ ] Can view permissions in page content?
   - [ ] What's in user_permissions context?

4. **Error Details:**
   - [ ] Browser console error (F12 > Console)
   - [ ] Template rendering issue
   - [ ] Link doesn't navigate

5. **Screenshots:**
   - [ ] What appears vs. what's expected

---

## ✅ Sign-Off Checklist

When you've completed testing, verify:

- [ ] Sidebar shows/hides based on permissions ✅
- [ ] Admin action cards appear on dashboard ✅
- [ ] Active links highlight correctly ✅
- [ ] Breadcrumbs show navigation trail ✅
- [ ] Mobile sidebar toggle works ✅
- [ ] Subscription status visible ✅
- [ ] All navigation links functional ✅
- [ ] No browser console errors ✅
- [ ] Mobile responsive at < 992px ✅

---

## 🎯 Expected Results Summary

**Desktop View (≥ 992px):**
```
┌─ NAVBAR (with workspace switcher, user menu) ─────────────────┐
├┬────────────────────────────────────────────────────────────┐─┤
││ SIDEBAR                    │ MAIN CONTENT AREA             ││
││ ─────────────────────────  │                               ││
││ Workspace Name             │ [Breadcrumbs]               ││
││ Role: Admin [badge]        │ [Dashboard Header]          ││
││                            │                               ││
││ Dashboard ✓ (active)       │ [Subscription Widget]       ││
││                            │ [Admin Actions Cards]       ││
││ TEAM                       │                               ││
││ ├─ Members                 │ [Dashboard Stats]           ││
││ └─ Invite Member           │ [Loans Summary]             ││
││                            │ [Team Section]              ││
││ WORKSPACE                  │                               ││
││ ├─ Settings                │                               ││
││ └─ Preferences             │                               ││
││                            │                               ││
││ BILLING                    │                               ││
││ └─ Subscription [Active]   │                               ││
││                            │                               ││
││ FEATURES                   │                               ││
││ ├─ Contacts                │                               ││
││ ├─ Girvi (Loans)           │                               ││
││ ├─ Sales                   │                               ││
││ ├─ Purchase                │                               ││
││ └─ Accounting              │                               ││
││                            │                               ││
││ Subscription:              │                               ││
││ ⓘ Active (Premium)         │                               ││
││ Renews in: 15 days         │                               ││
│└────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

**Mobile View (< 992px):**
```
┌─ NAVBAR ─────────────────────────────────┬──────┐
├──────────────────────────────────────────┤ [☰]  │
│ [Breadcrumbs]                            └──────┘
│ [Dashboard Header]
│
│ [Subscription Widget]
│ [Admin Actions Cards]
│
│ [Dashboard Stats]
│ [Loans Summary]
│ [Team Section]
│
│
└─ [Toggle Button] ─────────────────────────────────

[☰] Click → Opens sidebar from left:
┌─────────────────────┐
│ Navigation [✕]      │
├─────────────────────┤
│ Dashboard           │
│ Team > Members      │
│ Workspace > Sett... │
│ Billing > Subscr... │
│ Contacts            │
│ Girvi (Loans)       │
│ Sales               │
│ Purchase            │
│ Accounting          │
└─────────────────────┘
```

---

**Last Updated:** March 3, 2026  
**Version:** 1.0  
**Status:** Ready for Testing
