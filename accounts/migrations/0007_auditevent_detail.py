from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0006_onboarding_private_photo'),
    ]

    operations = [
        migrations.AddField(
            model_name='auditevent',
            name='detail',
            field=models.JSONField(default=dict),
        ),
    ]
