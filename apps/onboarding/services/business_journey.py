"""Presentation of existing saved setup; no separate completion state."""
from urllib.parse import urlencode

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from apps.onboarding.navigation import SETUP_PATHS, SETUP_STEPS


def build_business_journey(*, workspace, setup, query):
    path = query.get("path", "new")
    if path not in SETUP_PATHS:
        path = "new"
    base = reverse("workspace_slug_settings_setup", kwargs={"workspace_slug": workspace.slug})
    labels = (_("Your business"), _("Getting started"), _("Licence and numbering"),
              _("How you lend"), _("Interest and charges"), _("Review and begin"))
    first = setup["next_step"]
    default = {"business_profile": "business", "license": "starting", "series": "license",
               "economics": "terms", "product": "lending", "metal_rates": "terms"}.get(first["key"] if first else None, "review")
    step = query.get("step", default)
    if step not in SETUP_STEPS:
        step = default
    tabs = [dict(key=key, title=label, number=i + 1,
                 url=base + "?" + urlencode({"step": key, "path": path}), current=key == step)
            for i, (key, label) in enumerate(zip(SETUP_STEPS, labels))]
    index = SETUP_STEPS.index(step)
    action_groups = {"business_profile": "business", "license": "license", "series": "license",
                     "product": "lending", "economics": "terms", "metal_rates": "terms"}
    tasks = []
    for saved in setup["steps"]:
        task = dict(saved)
        group = action_groups[task["key"]]
        separator = "&" if "?" in task["action_url"].split("#")[0] else "?"
        url, *fragment = task["action_url"].split("#", 1)
        task["action_url"] = url + separator + urlencode({"setup_step": group, "setup_path": path})
        if fragment:
            task["action_url"] += "#" + fragment[0]
        task["group"] = group
        tasks.append(task)
    return dict(step=step, path=path, tabs=tabs, title=tabs[index]["title"], tasks=tasks,
        previous=tabs[index - 1] if index else None, following=tabs[index + 1] if index < 5 else None,
        choices=[dict(key=key, title=title, description=description,
                      url=base + "?" + urlencode({"step": "license", "path": key}))
                 for key, title, description in (
            ("new", _("Start with new loans"), _("Use Rokkad for loans you issue from now on. Existing paper loans can stay in your books.")),
            ("paper", _("Work alongside paper books"), _("Record earlier loans gradually, preserving their actual dates, numbers and agreed terms.")),
            ("import", _("Bring existing loans into Rokkad"), _("Use the supported register template, match customers and review balances before confirming an import.")),
        )])
