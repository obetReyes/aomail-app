# Generated by Django 5.1.6 on 2025-02-26 14:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aomail', '0004_preference_llm_provider_preference_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='preference',
            name='categorize_and_summarize_email_prompt',
            field=models.TextField(max_length=2000, null=True),
        ),
        migrations.AddField(
            model_name='preference',
            name='generate_email_prompt',
            field=models.TextField(max_length=1000, null=True),
        ),
        migrations.AddField(
            model_name='preference',
            name='generate_email_response_prompt',
            field=models.TextField(max_length=1000, null=True),
        ),
        migrations.AddField(
            model_name='preference',
            name='generate_response_keywords_prompt',
            field=models.TextField(max_length=1000, null=True),
        ),
        migrations.AddField(
            model_name='preference',
            name='improve_email_draft_prompt',
            field=models.TextField(max_length=1000, null=True),
        ),
        migrations.AddField(
            model_name='preference',
            name='improve_email_response_prompt',
            field=models.TextField(max_length=1000, null=True),
        ),
    ]