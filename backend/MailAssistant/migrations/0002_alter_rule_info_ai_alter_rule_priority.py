# Generated by Django 4.1.10 on 2023-11-24 22:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('MailAssistant', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='rule',
            name='info_AI',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='rule',
            name='priority',
            field=models.CharField(blank=True, max_length=50),
        ),
    ]
