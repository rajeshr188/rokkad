from django.contrib.postgres.indexes import GinIndex
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("data_portability", "0021_position_register_profiles")]
    operations = [migrations.AddIndex(model_name="importrow", index=GinIndex(
        fields=["canonical"], name="port_row_canonical_gin", opclasses=["jsonb_path_ops"],
        condition=models.Q(committed_at__isnull=False)))]
