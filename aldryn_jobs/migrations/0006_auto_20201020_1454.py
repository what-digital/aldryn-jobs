# Generated by Django 2.2.12 on 2020-10-20 12:54

import aldryn_jobs.models
import aldryn_translation_tools.models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django_countries.fields
import parler.fields
import parler.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('aldryn_jobs', '0005_auto_20200408_1343'),
    ]

    operations = [
        migrations.AddField(
            model_name='jobapplication',
            name='abc_analysis',
            field=models.CharField(blank=True, choices=[('A', 'A'), ('B', 'B'), ('C', 'C')], max_length=1, null=True, verbose_name='abc analysis'),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='abc_analysis_explaination',
            field=models.CharField(blank=True, max_length=200, null=True, verbose_name='abc analysis explaination'),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='answer_1',
            field=models.TextField(blank=True, null=True, verbose_name='answer 1'),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='answer_2',
            field=models.TextField(blank=True, null=True, verbose_name='answer 2'),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='answer_3',
            field=models.TextField(blank=True, null=True, verbose_name='answer 3'),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='application_pool',
            field=models.BooleanField(default=False, verbose_name='application pool'),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='city',
            field=models.CharField(default='', max_length=50, verbose_name='city'),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='country',
            field=django_countries.fields.CountryField(blank=True, max_length=2, null=True, verbose_name='country'),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='cover_letter_file',
            field=models.FileField(blank=True, max_length=200, null=True, upload_to=aldryn_jobs.models.default_jobs_attachment_upload_to, verbose_name='cover letter'),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='data_retention',
            field=models.CharField(blank=True, choices=[('Y', 'I agree that my data may be stored even beyond a specific vacancy and that I will be informed about interesting job offers.'), ('N', 'I would like my data to be deleted after the current application process.')], max_length=1, null=True, verbose_name='data retention'),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='expected_salary',
            field=models.TextField(blank=True, null=True, verbose_name='expected salary'),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='filled_by_rahn',
            field=models.BooleanField(default=False, verbose_name='filled by Rahn'),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='how_hear_about_us',
            field=models.CharField(blank=True, choices=[('linkedin', 'LinkedIn'), ('rahn website', 'RAHN Website'), ('other', 'Other (please specify) ')], max_length=12, null=True, verbose_name='how did you hear about us?'),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='how_hear_about_us_other',
            field=models.CharField(blank=True, max_length=20, null=True, verbose_name='other (how did you hear about us)'),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='merged_pdf',
            field=models.FileField(blank=True, max_length=200, null=True, upload_to=aldryn_jobs.models.default_jobs_attachment_upload_to, verbose_name='merged PDF of attachments'),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='mobile_phone',
            field=models.CharField(default='', max_length=20, verbose_name='mobile phone'),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='nationality',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='nationality'),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='notice_period',
            field=models.CharField(blank=True, choices=[('1', '1 month'), ('2', '2 month'), ('3', '3 month'), ('6', '6 month'), ('0', 'None'), ('O', 'Others')], max_length=1, null=True, verbose_name='notice period'),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='status',
            field=models.CharField(blank=True, choices=[('rejection rahn ag', 'Rejection Rahn AG'), ('rejection_candidate', 'Rejection Candidate'), ('confirmation receiving', 'Confirmation of receiving'), ('maybe later', 'Maybe later'), ('contaact', 'Contact'), ('1st interview', '1st interview'), ('2st interview', '2nd interview'), ('3st interview', '3rd interview'), ('missing document', 'Missing documents'), ('employement contract', 'Employment Contract'), ('shared with superior', 'Shared with superiors')], max_length=25, null=True, verbose_name='status'),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='street',
            field=models.CharField(default='', max_length=200, verbose_name='street'),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='valid_work_permit',
            field=models.CharField(blank=True, choices=[('yes', 'Yes'), ('no', 'No')], max_length=3, null=True, verbose_name='valid work permit'),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='zipcode',
            field=models.CharField(default='', max_length=10, verbose_name='zip code'),
        ),
        migrations.AddField(
            model_name='jobopening',
            name='country',
            field=models.CharField(choices=[('germany', 'Germany'), ('switzerland', 'Switzerland'), ('china', 'China'), ('uk', 'United Kingdom'), ('france', 'France'), ('usa', 'USA')], default='germany', max_length=100, verbose_name='country'),
        ),
        migrations.AddField(
            model_name='jobopening',
            name='reminder_mail_sent',
            field=models.BooleanField(default=False, verbose_name='reminder mail sent'),
        ),
        migrations.AddField(
            model_name='jobopening',
            name='responsibles',
            field=models.ManyToManyField(blank=True, limit_choices_to={'is_staff': True}, to=settings.AUTH_USER_MODEL, verbose_name='responsibles'),
        ),
        migrations.AddField(
            model_name='jobopening',
            name='vacancy_filled',
            field=models.BooleanField(default=False, verbose_name='vacancy filled'),
        ),
        migrations.AddField(
            model_name='jobopening',
            name='vacancy_filled_date',
            field=models.DateTimeField(blank=True, null=True, verbose_name='vacancy filled since'),
        ),
        migrations.AlterField(
            model_name='jobapplication',
            name='cover_letter',
            field=models.TextField(blank=True, null=True, verbose_name='cover letter'),
        ),
        migrations.CreateModel(
            name='JobOpeningQuestion',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('job_opening', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='questions', to='aldryn_jobs.JobOpening', verbose_name='job opening')),
            ],
            options={
                'verbose_name_plural': 'job opening questions',
                'verbose_name': 'job opening question',
            },
            bases=(aldryn_translation_tools.models.TranslationHelperMixin, parler.models.TranslatableModelMixin, models.Model),
        ),
        migrations.CreateModel(
            name='JobOpeningQuestionTranslation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('language_code', models.CharField(db_index=True, max_length=15, verbose_name='Language')),
                ('question', models.TextField(verbose_name='question')),
                ('master', parler.fields.TranslationsForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='translations', to='aldryn_jobs.JobOpeningQuestion')),
            ],
            options={
                'unique_together': {('language_code', 'master')},
                'db_table': 'aldryn_jobs_jobopeningquestion_translation',
                'verbose_name': 'job opening question Translation',
                'db_tablespace': '',
                'managed': True,
                'default_permissions': (),
            },
            bases=(parler.models.TranslatedFieldsModelMixin, models.Model),
        ),
    ]