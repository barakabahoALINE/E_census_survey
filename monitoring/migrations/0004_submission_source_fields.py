from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("monitoring", "0003_submission_district"),
    ]

    operations = [
        migrations.AddField(
            model_name="submission",
            name="source_national_id",
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name="submission",
            name="source_record_id",
            field=models.PositiveBigIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="submission",
            name="phone_number",
            field=models.CharField(blank=True, max_length=30),
        ),
    ]