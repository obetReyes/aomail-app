# Generated by Django 4.1.10 on 2024-01-13 10:36

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('MailAssistant', '0003_alter_rule_category'),
    ]

    operations = [
        migrations.AlterField(
            model_name='rule',
            name='category',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='MailAssistant.category'),
        ),
    ]
