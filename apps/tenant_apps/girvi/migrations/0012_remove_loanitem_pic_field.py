from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("girvi", "0011_add_loan_item_pic_relationships"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="loanitem",
            name="pic",
        ),
    ]