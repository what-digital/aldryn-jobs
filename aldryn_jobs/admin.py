# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from django.conf import settings
from django.contrib import admin
from django.contrib.sites.shortcuts import get_current_site
from django.db import models
from django.utils.safestring import mark_safe
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _

from adminsortable2.admin import SortableAdminMixin
from aldryn_apphooks_config.admin import BaseAppHookConfig
from aldryn_translation_tools.admin import (
    AllTranslationsMixin,
    LinkedRelatedInlineMixin,
)

from cms.admin.placeholderadmin import PlaceholderAdminMixin, FrontendEditableAdminMixin

from emailit.api import send_mail
from parler.admin import TranslatableAdmin, TranslatableStackedInline


from .forms import JobCategoryAdminForm, JobOpeningAdminForm
from .models import JobApplication, JobCategory, JobOpening, JobOpeningQuestion, JobsConfig, NewsletterSignup


def _send_rejection_email(modeladmin, request, queryset, lang_code='',
                          delete_application=False, application_pool=False):
    qs_count = len(queryset)

    for application in queryset:
        mail_template = 'aldryn_jobs/emails/rejection_letter' if not application_pool else \
            'aldryn_jobs/emails/rejection_letter_application_pool'
        context = {'job_application': application, }
        send_mail(recipients=[application.email], context=context,
                  template_base=mail_template,
                  language=lang_code.lower())

    if not delete_application:
        queryset.update(
            is_rejected=True,
            rejection_date=now(),
            status='rejection rahn ag',
            application_pool=application_pool
        )
        success_msg = _("Successfully sent {0} rejection email(s).").format(qs_count)
    else:
        queryset.delete()
        success_msg = _("Successfully deleted {0} application(s) and sent "
                        "rejection email.").format(qs_count)

    modeladmin.message_user(request, success_msg)
    return


class SendRejectionEmail(object):

    def __init__(self, lang_code=''):
        super(SendRejectionEmail, self).__init__()
        self.lang_code = lang_code.upper()
        self.name = 'send_rejection_email_{0}'.format(self.lang_code)
        self.title = _("Send rejection e-mail {0}").format(self.lang_code)

    def __call__(self, modeladmin, request, queryset, *args, **kwargs):
        _send_rejection_email(modeladmin, request, queryset,
                              lang_code=self.lang_code)


class SendRejectionEmailApplicationPool(object):

    def __init__(self, lang_code=''):
        super(SendRejectionEmailApplicationPool, self).__init__()
        self.lang_code = lang_code.upper()
        self.name = 'send_rejection_email_application_pool_{0}'.format(self.lang_code)
        self.title = _("Send rejection e-mail (Application pool) {0}").format(self.lang_code)

    def __call__(self, modeladmin, request, queryset, *args, **kwargs):
        _send_rejection_email(modeladmin, request, queryset,
                              lang_code=self.lang_code, application_pool=True)


class SendRejectionEmailAndDelete(SendRejectionEmail):

    def __init__(self, lang_code=''):
        super(SendRejectionEmailAndDelete, self).__init__(lang_code)
        self.name = 'send_rejection_and_delete_{0}'.format(self.lang_code)
        self.title = _("Send rejection e-mail and delete "
                       "application {0}").format(self.lang_code)

    def __call__(self, modeladmin, request, queryset, *args, **kwargs):
        _send_rejection_email(modeladmin, request, queryset,
                              lang_code=self.lang_code, delete_application=True)


class JobApplicationAdmin(PlaceholderAdminMixin, admin.ModelAdmin):
    list_display = ['__str__', 'job_opening', 'created', 'is_rejected',
                    'rejection_date', ]
    list_filter = ['job_opening', 'is_rejected']
    readonly_fields = ['get_attachment_address']
    raw_id_fields = ['job_opening']

    fieldsets = [
        (_('Job Opening'), {
            'fields': [('job_opening', 'status', 'filled_by_rahn')]
        }),
        (_('Personal information'), {
            'fields': [
                ('salutation', 'first_name', 'last_name', 'email'),
                ('street', 'city', 'zipcode'),
                ('country', 'nationality', 'mobile_phone', 'valid_work_permit'),
            ]
        }),
        (_('Cover letter & attachments'), {
            'fields': [
                'cover_letter', 'cover_letter_file', 'get_attachment_address', 'merged_pdf'
            ]
        }),
        (_('Questions and data'), {
            'fields': [
                'answer_1', 'answer_2', 'answer_3', 'expected_salary',
                ('notice_period', 'how_hear_about_us', 'how_hear_about_us_other'),
                'data_retention',
                ('application_pool', 'abc_analysis', 'abc_analysis_explanation'),
            ]
        })
    ]

    def get_actions(self, request):
        actions = super(JobApplicationAdmin, self).get_actions(request)
        language_codes = [language[0] for language in settings.LANGUAGES]
        for lang_code in language_codes:
            send_rejection_email = SendRejectionEmail(lang_code=lang_code)
            actions[send_rejection_email.name] = (
                send_rejection_email,
                send_rejection_email.name,
                send_rejection_email.title
            )
            send_rejection_email_application_pool = SendRejectionEmailApplicationPool(lang_code=lang_code)
            actions[send_rejection_email_application_pool.name] = (
                send_rejection_email_application_pool,
                send_rejection_email_application_pool.name,
                send_rejection_email_application_pool.title
            )
            send_rejection_and_delete = SendRejectionEmailAndDelete(
                lang_code=lang_code)
            actions[send_rejection_and_delete.name] = (
                send_rejection_and_delete,
                send_rejection_and_delete.name,
                send_rejection_and_delete.title
            )
        return actions

    def get_attachment_address(self, instance):
        attachment_link = '<a href="{address}">{address}</a>'
        attachments = []

        for attachment in instance.attachments.all():
            if attachment:
                attachments.append(
                    attachment_link.format(address=attachment.file.url))
        return mark_safe('<br>'.join(attachments)) if attachments else '-'

    get_attachment_address.allow_tags = True
    get_attachment_address.short_description = _('Attachments')


class JobCategoryAdmin(PlaceholderAdminMixin,
                       SortableAdminMixin, AllTranslationsMixin,
                       TranslatableAdmin):
    form = JobCategoryAdminForm
    list_display = ['__str__', 'app_config']
    filter_horizontal = ['supervisors']

    def get_fieldsets(self, request, obj=None):
        fieldsets = [
            (_('Translatable fields'), {
                'fields': ['name', 'slug']
            }),
            (_('Supervisors'), {
                'fields': ['supervisors']
            }),
            (_('Options'), {
                'fields': ['app_config']
            })
        ]
        return fieldsets


class JobApplicationInline(LinkedRelatedInlineMixin, admin.TabularInline):
    model = JobApplication
    fields = ['email', 'is_rejected', ]
    readonly_fields = ['email', 'is_rejected', ]

    def has_add_permission(self, request, obj):
        return False


class JobOpeningQuestionInline(TranslatableStackedInline):
    model = JobOpeningQuestion
    fields = ['question']
    max_num = 3


class JobOpeningAdmin(PlaceholderAdminMixin,
                      AllTranslationsMixin,
                      SortableAdminMixin,
                      FrontendEditableAdminMixin,
                      TranslatableAdmin):
    form = JobOpeningAdminForm
    list_display = ['__str__', 'category', 'num_applications']
    frontend_editable_fields = ('title', 'lead_in')
    inlines = [JobOpeningQuestionInline, JobApplicationInline]
    actions = ['send_newsletter_email']

    def get_fieldsets(self, request, obj=None):
        fieldsets = [
            (_('Translatable fields'), {
                'fields': ['title', 'meta_description', 'hide_link', 'slug', 'lead_in']
            }),
            (_('Options'), {
                'fields': ['category', 'is_active', 'can_apply', 'country']
            }),
            (_('Publication period'), {
                'fields': [('publication_start', 'publication_end')]
            }),
            (_('Vacancy filled'), {
                'fields': [
                    'vacancy_filled', 'vacancy_filled_date',
                    'reminder_mail_sent', 'responsibles',
                ]
            })
        ]
        return fieldsets

    def get_queryset(self, request):
        qs = super(JobOpeningAdmin, self).get_queryset(request)
        qs = qs.annotate(applications_count=models.Count('applications'))
        return qs

    def num_applications(self, obj):
        return obj.applications_count
    num_applications.short_description = '# Applications'
    num_applications.admin_order_field = 'applications_count'

    def send_newsletter_email(self, request, queryset):
        """
        Sends a newsletter to all active recipients.
        """
        # FIXME: this will use admin's domain instead of language specific
        # if site has multiple domains for different languages
        current_domain = get_current_site(request).domain

        job_list = [job.pk for job in queryset]
        sent_emails = NewsletterSignup.objects.send_job_notifiation(
            job_list=job_list, current_domain=current_domain)

        jobs_sent = len(job_list)
        if jobs_sent == 1:
            message_bit = _("1 job was")
        else:
            message_bit = _('{0} jobs were').format(jobs_sent)
        if sent_emails > 0:
            self.message_user(request,
                              _("{0} successfully sent in the newsletter.").format(
                                  message_bit))
        else:
            self.message_user(request,
                              _('Seems there was some error. Please contact administrator'))

    send_newsletter_email.short_description = _("Send Job Newsletter")


class JobNewsletterSignupAdmin(PlaceholderAdminMixin,
                               admin.ModelAdmin):
    list_display = ['recipient', 'default_language', 'signup_date',
                    'is_verified', 'is_disabled']
    order_by = ['recipient']


class JobsConfigAdmin(PlaceholderAdminMixin, BaseAppHookConfig):
    pass


admin.site.register(JobApplication, JobApplicationAdmin)
admin.site.register(JobCategory, JobCategoryAdmin)
admin.site.register(JobOpening, JobOpeningAdmin)
admin.site.register(JobsConfig, JobsConfigAdmin)
admin.site.register(NewsletterSignup, JobNewsletterSignupAdmin)
