# Generated by Django 4.1.10 on 2024-01-10 12:11

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('MailAssistant', '0002_alter_rule_info_ai_alter_rule_priority'),
    ]

    operations = [
        migrations.CreateModel(
            name='CredsAPI',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('access_token', models.CharField(max_length=500)),
                ('refresh_token', models.CharField(max_length=500)),
                ('social_api', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='MailAssistant.socialapi')),
            ],
        ),
    ]
