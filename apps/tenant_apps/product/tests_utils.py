from .models import Movement


def ensure_inventory_movements():
    movements = {
        "P": ("Purchase", "+"),
        "PR": ("Purchase Return", "-"),
        "S": ("Sales", "-"),
        "SR": ("Sales Return", "+"),
        "A": ("Approval", "-"),
        "AR": ("Approval Return", "+"),
        "AD": ("Add", "+"),
        "R": ("Remove", "-"),
        "RM": ("Merge Remove", "-"),
        "SS": ("Split Separate", "-"),
        "OB": ("Opening Balance", "+"),
    }
    for movement_id, (name, direction) in movements.items():
        Movement.objects.update_or_create(
            id=movement_id,
            defaults={"name": name, "direction": direction},
        )
