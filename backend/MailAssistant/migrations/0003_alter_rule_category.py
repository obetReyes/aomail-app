# Generated by Django 4.1.10 on 2024-01-13 10:14

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('MailAssistant', '0002_alter_rule_info_ai_alter_rule_priority'),
    ]

    operations = [
        migrations.AlterField(
            model_name='rule',
            name='category',
            field=models.ForeignKey(blank=True, on_delete=django.db.models.deletion.CASCADE, to='MailAssistant.category'),
        ),
    ]
