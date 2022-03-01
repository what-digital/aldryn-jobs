# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django import get_version
from django.conf import settings
from django.urls import reverse, NoReverseMatch

from django.db import models
from django.db.models.signals import pre_delete, post_save
from django.dispatch.dispatcher import receiver
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _, pgettext_lazy
from django.contrib.auth.models import Group, User
from django.contrib.sites.shortcuts import get_current_site
from django.http import Http404
from emailit.api import send_mail


from djangocms_text_ckeditor.fields import HTMLField
from aldryn_apphooks_config.managers.parler import (
    AppHookConfigTranslatableManager
)
from aldryn_translation_tools.models import (
    TranslationHelperMixin, TranslatedAutoSlugifyMixin,
)

from cms.models import CMSPlugin
from cms.models.fields import PlaceholderField
from cms.utils.i18n import force_language
from django_countries.fields import CountryField
from distutils.version import LooseVersion
from functools import partial
from os.path import join as join_path
from parler.models import TranslatableModel, TranslatedFields
from sortedm2m.fields import SortedManyToManyField
from uuid import uuid4

from .cms_appconfig import JobsConfig
from .managers import JobOpeningsManager, NewsletterSignupManager
from .utils import get_valid_filename

# NOTE: We need to use LooseVersion NOT StrictVersion as Aldryn sometimes uses
# patched versions of Django with version numbers in the form: X.Y.Z.postN
loose_version = LooseVersion(get_version())


# We should check if user model is registered, since we're following on that
# relation for EventCoordinator model, if not - register it to
# avoid RegistrationError when registering models that refer to it.
user_model = getattr(settings, 'AUTH_USER_MODEL', 'auth.User')


def default_jobs_attachment_upload_to(instance, filename):
    date = now().strftime('%Y/%m')
    return join_path(
        'attachments', date, str(uuid4()), get_valid_filename(filename)
    )


jobs_attachment_upload_to = getattr(
    settings, 'ALDRYN_JOBS_ATTACHMENT_UPLOAD_DIR',
    default_jobs_attachment_upload_to
)

jobs_attachment_storage = getattr(
    settings, 'ALDRYN_JOBS_ATTACHMENT_STORAGE', None
)

JobApplicationFileField = partial(
    models.FileField,
    max_length=200,
    blank=True,
    null=True,
    upload_to=jobs_attachment_upload_to,
    storage=jobs_attachment_storage,

)


class JobCategory(TranslatedAutoSlugifyMixin,
                  TranslationHelperMixin,
                  TranslatableModel):
    slug_source_field_name = 'name'

    translations = TranslatedFields(
        name=models.CharField(_('name'), max_length=255),
        slug=models.SlugField(
            _('slug'), max_length=255, blank=True,
            help_text=_('Auto-generated. Used in the URL. If changed, the URL '
                        'will change. Clear it to have the slug re-created.'))
    )

    supervisors = models.ManyToManyField(
        getattr(settings, 'AUTH_USER_MODEL', 'auth.User'), verbose_name=_('supervisors'),
        # FIXME: This is mis-named should be "job_categories"?
        related_name='job_opening_categories',
        help_text=_('Supervisors will be notified via email when a new '
                    'job application arrives.'),
        blank=True
    )
    app_config = models.ForeignKey(
        JobsConfig,
        null=True,
        verbose_name=_('app configuration'),
        related_name='categories',
        on_delete=models.CASCADE
    )

    ordering = models.IntegerField(_('ordering'), default=0)

    objects = AppHookConfigTranslatableManager()

    class Meta:
        verbose_name = _('job category')
        verbose_name_plural = _('job categories')
        ordering = ['ordering']

    def __str__(self):
        return self.safe_translation_getter('name', str(self.pk))

    def _slug_exists(self, *args, **kwargs):
        """Provide additional filtering for slug generation"""
        qs = kwargs.get('qs', None)
        if qs is None:
            qs = self._get_slug_queryset()
        # limit qs to current app_config only
        kwargs['qs'] = qs.filter(app_config=self.app_config)
        return super(JobCategory, self)._slug_exists(*args, **kwargs)

    def get_absolute_url(self, language=None):
        language = language or self.get_current_language()
        slug = self.safe_translation_getter('slug', language_code=language)
        if self.app_config_id:
            namespace = self.app_config.namespace
        else:
            namespace = 'aldryn_jobs'
        with force_language(language):
            try:
                if not slug:
                    return reverse('{0}:job-opening-list'.format(namespace))
                kwargs = {'category_slug': slug}
                return reverse(
                    '{0}:category-job-opening-list'.format(namespace),
                    kwargs=kwargs,
                    current_app=self.app_config.namespace
                )
            except NoReverseMatch:
                return "/%s/" % language

    def get_notification_emails(self):
        return self.supervisors.values_list('email', flat=True)

    # We keep this 'count' name for compatibility in templates:
    # there used to be annotate() call with the same property name.
    def count(self):
        return self.jobs.active().count()


class JobOpening(TranslatedAutoSlugifyMixin,
                 TranslationHelperMixin,
                 TranslatableModel):
    COUNTRIES = (
        ('germany', _('Germany')),
        ('switzerland', _('Switzerland')),
        ('china', _('China')),
        ('uk', _('United Kingdom')),
        ('france', _('France')),
        ('usa', _('USA'))
    )

    slug_source_field_name = 'title'

    translations = TranslatedFields(
        title=models.CharField(_('title'), max_length=255),
        meta_description=models.CharField(_("meta description"), max_length=155, null=True, blank=True),
        slug=models.SlugField(
            _('slug'), max_length=255, blank=True,
            unique=False, db_index=False,
            help_text=_('Auto-generated. Used in the URL. If changed, the URL '
                        'will change. Clear it to have the slug re-created.')),
        lead_in=HTMLField(
            _('short description'), blank=True,
            help_text=_('This text will be displayed in lists.')),
        hide_link=models.BooleanField(_('hide link in jobs list'), default=False)
    )

    content = PlaceholderField('Job Opening Content')
    category = models.ForeignKey(
        JobCategory,
        verbose_name=_('category'),
        related_name='jobs',
        on_delete=models.CASCADE
    )
    created = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(_('active?'), default=True)
    vacancy_filled = models.BooleanField(_('vacancy filled'), default=False)
    vacancy_filled_date = models.DateTimeField(_('vacancy filled since'), null=True, blank=True)
    reminder_mail_sent = models.BooleanField(_('reminder mail sent'), default=False)
    responsibles = models.ManyToManyField(
        User, verbose_name=_('responsibles'), limit_choices_to={'groups__name': 'Rahn HR Responsibles'}, blank=True
    )
    publication_start = models.DateTimeField(_('published since'), null=True, blank=True)
    publication_end = models.DateTimeField(_('published until'), null=True, blank=True)
    can_apply = models.BooleanField(_('viewer can apply for the job?'), default=True)
    country = models.CharField(_('country'), choices=COUNTRIES, max_length=100, default='germany')

    ordering = models.IntegerField(_('ordering'), default=0)

    objects = JobOpeningsManager()

    class Meta:
        verbose_name = _('job opening')
        verbose_name_plural = _('job openings')
        # DO NOT attempt to add 'translated__title' here.
        ordering = ['ordering', ]

    def __str__(self):
        return self.safe_translation_getter('title', str(self.pk))

    def _slug_exists(self, *args, **kwargs):
        """Provide additional filtering for slug generation"""
        qs = kwargs.get('qs', None)
        if qs is None:
            qs = self._get_slug_queryset()
        # limit qs to current app_config only
        kwargs['qs'] = qs.filter(category__app_config=self.category.app_config)
        return super(JobOpening, self)._slug_exists(*args, **kwargs)

    def get_absolute_url(self, language=None):
        language = language or self.get_current_language()
        slug = self.safe_translation_getter('slug', language_code=language)
        category_slug = self.category.safe_translation_getter(
            'slug', language_code=language
        )
        namespace = getattr(
            self.category.app_config, "namespace", "aldryn_jobs")
        with force_language(language):
            try:
                # FIXME: does not looks correct return category url here
                if not slug:
                    return self.category.get_absolute_url(language=language)
                kwargs = {
                    'category_slug': category_slug,
                    'job_opening_slug': slug,
                }
                return reverse(
                    '{0}:job-opening-detail'.format(namespace),
                    kwargs=kwargs,
                    current_app=namespace
                )
            except NoReverseMatch:
                # FIXME: this is wrong, if have some problem in reverse
                #        we should know
                return "/%s/" % language

    def get_active(self):
        return all([
            self.is_active,
            self.publication_start is None or self.publication_start <= now(),
            self.publication_end is None or self.publication_end > now()
        ])

    def get_notification_emails(self):
        return self.category.get_notification_emails()


@receiver(post_save, sender=JobOpening)
def set_vacancy_filled_date(sender, instance, update_fields, **kwargs):
    if not instance:
        return
    if hasattr(instance, '_dirty'):
        return

    if instance.vacancy_filled and not instance.vacancy_filled_date:
        instance.vacancy_filled_date = now()

    try:
        instance._dirty = True
        instance.save()
    finally:
        del instance._dirty


class JobOpeningQuestion(TranslationHelperMixin, TranslatableModel):
    job_opening = models.ForeignKey(
        JobOpening,
        related_name='questions',
        verbose_name=_('job opening'),
        on_delete=models.CASCADE
    )
    translations = TranslatedFields(
        question=models.TextField(_('question')),
    )

    class Meta:
        verbose_name = _('job opening question')
        verbose_name_plural = _('job opening questions')

    def __str__(self):
        return self.safe_translation_getter('question', str(self.pk))


class JobApplication(models.Model):
    # FIXME: Gender is not the same as salutation.
    MALE = 'male'
    FEMALE = 'female'

    DATA_RETENTION_YES = _('I agree that my data may be stored even beyond a specific vacancy and that I will be'
                           ' informed about interesting job offers.')
    DATA_RETENTION_NO = _('I would like my data to be deleted after the current application process.')

    SALUTATION_CHOICES = (
        ('', _('Please select')),
        (MALE, _('Mr.')),
        (FEMALE, _('Mrs.')),
    )

    VALID_WORK_PERMIT_CHOICES = (
        ('', _('Please select')),
        ('yes', _('Yes')),
        ('no', _('No'))
    )

    NOTICE_PERIOD_CHOICES = (
        ('', _('Please select')),
        ('1 month', _('1 month')),
        ('2 months', _('2 months')),
        ('3 months', _('3 months')),
        ('6 months', _('6 months')),
        ('none', pgettext_lazy('None in notice period', 'None')),
        ('other', _('Other (please specify)'))
    )

    HOW_HEAR_ABOUT_US_CHOICES = (
        ('', _('Please select')),
        ('linkedin', _('LinkedIn')),
        ('rahn website', _('RAHN Website')),
        ('other', _('Other (please specify) ')),
    )

    DATA_RETENTION_CHOICES = (
        ('Y', DATA_RETENTION_YES),
        ('N', DATA_RETENTION_NO),
    )

    ABC_ANALYSIS_CHOICES = (
        ('A', 'A'),
        ('AB', 'AB'),
        ('B', 'B'),
        ('BC', 'BC'),
        ('C', 'C'),
    )

    STATUS_CHOICES = (
        ('rejection rahn ag', _('Rejection Rahn AG')),
        ('rejection_candidate', _('Rejection Candidate')),
        ('confirmation receiving', _('Confirmation of receiving')),
        ('maybe later', _('Maybe later')),
        ('contaact', _('Contact')),
        ('1st interview', _('1st interview')),
        ('2st interview', _('2nd interview')),
        ('3st interview', _('3rd interview')),
        ('missing document', _('Missing documents')),
        ('employement contract', _('Employment Contract')),
        ('shared with superior', _('Shared with superiors'))
    )

    job_opening = models.ForeignKey(
        JobOpening,
        related_name='applications',
        on_delete=models.CASCADE
    )
    salutation = models.CharField(_('salutation'), max_length=20, null=True, blank=True, choices=SALUTATION_CHOICES)
    first_name = models.CharField(_('first name'), max_length=20)
    last_name = models.CharField(_('last name'), max_length=20)
    email = models.EmailField(_('email'), max_length=254)
    street = models.CharField(_('street'), max_length=200, default='')
    city = models.CharField(_('city'), max_length=50, default='')
    zipcode = models.CharField(_('zip code'), max_length=10, default='')
    country = CountryField(_('country'), null=True, blank=True)
    nationality = models.CharField(_('nationality'), max_length=50, null=True, blank=True)
    mobile_phone = models.CharField(_('phone number'), max_length=20, default='')
    valid_work_permit = models.CharField(
        _('valid work permit'),
        choices=VALID_WORK_PERMIT_CHOICES,
        max_length=3,
        null=True,
        blank=True
    )
    cover_letter_file = models.FileField(
        _('cover letter'),
        max_length=200,
        blank=True,
        null=True,
        upload_to=jobs_attachment_upload_to,
        storage=jobs_attachment_storage
    )
    cover_letter = models.TextField(_('cover letter'), null=True, blank=True)
    answer_1 = models.TextField(_('answer 1'), null=True, blank=True)
    answer_2 = models.TextField(_('answer 2'), null=True, blank=True)
    answer_3 = models.TextField(_('answer 3'), null=True, blank=True)
    expected_salary = models.TextField(_('expected salary'), blank=True, null=True)
    notice_period = models.CharField(
        _('notice period'),
        choices=NOTICE_PERIOD_CHOICES,
        max_length=10,
        null=True,
        blank=True
    )
    notice_period_other = models.CharField(
        _('other (notice period)'), max_length=256, null=True, blank=True
    )
    how_hear_about_us = models.CharField(
        _('how did you hear about us?'),
        choices=HOW_HEAR_ABOUT_US_CHOICES,
        max_length=12,
        null=True,
        blank=True
    )
    how_hear_about_us_other = models.CharField(
        _('other (how did you hear about us)'), max_length=50, null=True, blank=True
    )
    data_retention = models.CharField(
        _('data retention'),
        choices=DATA_RETENTION_CHOICES,
        max_length=1,
        null=True,
        blank=True
    )
    application_pool = models.BooleanField(_('application pool'), default=False)
    abc_analysis = models.CharField(
        _('abc analysis'),
        choices=ABC_ANALYSIS_CHOICES,
        max_length=2,
        null=True,
        blank=True
    )
    abc_analysis_explanation = models.CharField(_('abc analysis explanation'), max_length=200, null=True, blank=True)
    status = models.CharField(_('status'), choices=STATUS_CHOICES, max_length=25, null=True, blank=True)
    filled_by_rahn = models.BooleanField(_('filled by Rahn'), default=False)
    created = models.DateTimeField(_('created'), auto_now_add=True)
    is_rejected = models.BooleanField(_('rejected?'), default=False)
    rejection_date = models.DateTimeField(_('rejection date'), null=True, blank=True)
    merged_pdf = models.FileField(
        _('merged PDF of attachments'),
        max_length=200,
        blank=True,
        null=True,
        upload_to=jobs_attachment_upload_to,
        storage=jobs_attachment_storage
    )

    class Meta:
        ordering = ['-created']
        verbose_name = _('job application')
        verbose_name_plural = _('job applications')

    def __str__(self):
        return self.get_full_name()

    def get_full_name(self):
        full_name = ' '.join([self.first_name, self.last_name])
        return full_name.strip()

    @property
    def business_area(self):
        return self.job_opening.category

    @property
    def data_retention_value(self):
        if self.data_retention == 'Y':
            return _('Yes')
        elif self.data_retention == 'N':
            return _('No')
        return ''


@receiver(pre_delete, sender=JobApplication)
def cleanup_attachments(sender, instance, **kwargs):
    for attachment in instance.attachments.all():
        if attachment:
            attachment.file.delete(False)


class JobApplicationAttachment(models.Model):
    application = models.ForeignKey(
        JobApplication,
        related_name='attachments',
        verbose_name=_('job application'),
        on_delete=models.CASCADE
    )
    file = JobApplicationFileField()


class NewsletterSignup(models.Model):
    recipient = models.EmailField(_('recipient'), unique=True)
    default_language = models.CharField(_('language'), blank=True,
        default='', max_length=32, choices=settings.LANGUAGES)
    signup_date = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)
    is_disabled = models.BooleanField(default=False)
    confirmation_key = models.CharField(max_length=40, unique=True)

    app_config = models.ForeignKey(
        JobsConfig,
        verbose_name=_('app_config'),
        null=True,
        on_delete=models.CASCADE
    )

    objects = NewsletterSignupManager()

    def get_absolute_url(self):
        kwargs = {'key': self.confirmation_key}
        with force_language(self.default_language):
            try:
                url = reverse(
                    '{0}:confirm_newsletter_email'.format(
                        self.app_config.namespace),
                    kwargs=kwargs
                )
            except NoReverseMatch:
                try:
                    url = reverse(
                        '{0}:confirm_newsletter_not_found'.format(
                            self.app_config.namespace))
                except NoReverseMatch:
                    raise Http404()
        return url

    def reset_confirmation(self):
        """ Reset the confirmation key.
        Note that the old key won't work anymore
        """
        update_fields = ['confirmation_key', ]
        self.confirmation_key = NewsletterSignup.objects.generate_random_key()
        # check if user was in the mailing list but then disabled newsletter
        # and now wants to get it again
        if self.is_verified and self.is_disabled:
            self.is_disabled = False
            self.is_verified = False
            update_fields.extend(['is_disabled', 'is_verified'])
        self.save(update_fields=update_fields)
        self.send_newsletter_confirmation_email()

    def send_newsletter_confirmation_email(self, request=None):
        context = {
            'data': self,
            'full_name': None,
        }
        # check if we have a user somewhere
        user = None
        if hasattr(self, 'user'):
            user = self.user
        elif request is not None and request.user.is_authenticated:
            user = request.user
        elif self.related_user.filter(signup__pk=self.pk):
            user = self.related_user.filter(signup__pk=self.pk).get()

        if user:
            context['full_name'] = user.get_full_name()

        # get site domain
        full_link = '{0}{1}'.format(
            get_current_site(request).domain,
            self.get_absolute_url()
        )
        context['link'] = self.get_absolute_url()
        context['full_link'] = full_link
        # build url
        send_mail(recipients=[self.recipient],
                  context=context,
                  language=self.default_language,
                  template_base='aldryn_jobs/emails/newsletter_confirmation')

    def confirm(self):
        """
        Confirms NewsletterSignup, excepts that is_verified is checked before
        calling this method.
        """
        self.is_verified = True
        self.save(update_fields=['is_verified', ])

    def disable(self):
        self.is_disabled = True
        self.save(update_fields=['is_disabled', ])

    def __str__(self):
        return '{0} / {1}'.format(self.recipient, self.app_config)


class NewsletterSignupUser(models.Model):
    signup = models.ForeignKey(
        NewsletterSignup,
        related_name='related_user',
        on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        getattr(settings, 'AUTH_USER_MODEL', 'auth.User'),
        related_name='newsletter_signup',
        on_delete=models.CASCADE
    )

    def get_full_name(self):
        return self.user.get_full_name()

    def __str__(self):
        return 'link to user {0}'.format(self.get_full_name())


class JobListPlugin(CMSPlugin):
    """ Store job list for JobListPlugin. """

    cmsplugin_ptr = models.OneToOneField(
        CMSPlugin,
        related_name='aldryn_jobs_joblistplugin',
        parent_link=True,
        on_delete=models.CASCADE
    )

    app_config = models.ForeignKey(
        JobsConfig,
        verbose_name=_('app configuration'), null=True,
        help_text=_('Select appropriate app. configuration for this plugin.'),
        on_delete=models.CASCADE
    )

    jobopenings = SortedManyToManyField(
        JobOpening, blank=True,
        verbose_name=_('job openings'),
        help_text=_("Choose specific Job Openings to show or leave empty to "
                    "show latest. Note that Job Openings from different "
                    "app configs will not appear."))

    def __str__(self):
        return str(self.pk)

    def get_job_openings(self, namespace):
        """
        Return the selected JobOpening for JobListPlugin.

        If no JobOpening are selected, return all active events for namespace
        and language, sorted by title.
        """
        if self.jobopenings.exists():
            return self.jobopenings.namespace(namespace).active()

        return (
            JobOpening.objects.namespace(namespace)
                              .language(self.language)
                              .active_translations(self.language)
                              .active()
        )

    def copy_relations(self, oldinstance):
        self.app_config = oldinstance.app_config
        self.jobopenings.set(oldinstance.jobopenings.all())


class JobCategoriesPlugin(CMSPlugin):

    cmsplugin_ptr = models.OneToOneField(
        CMSPlugin, related_name='aldryn_jobs_jobcategoriesplugin',
        parent_link=True,
        on_delete=models.CASCADE
    )

    app_config = models.ForeignKey(
        JobsConfig,
        verbose_name=_('app configuration'), null=True,
        help_text=_('Select appropriate app. configuration for this plugin.'),
        on_delete=models.CASCADE
    )

    def __str__(self):
        return _('%s categories') % (self.app_config.namespace,)

    @property
    def categories(self):
        categories_qs = JobCategory.objects.namespace(
            self.app_config.namespace).order_by('ordering')
        return (category for category in categories_qs if category.count())

    def copy_relations(self, oldinstance):
        self.app_config = oldinstance.app_config


class JobNewsletterRegistrationPlugin(CMSPlugin):
    app_config = models.ForeignKey(
        JobsConfig,
        verbose_name=_('app_config'),
        null=True, help_text=_('Select appropriate add-on configuration for this plugin.'),
        on_delete=models.CASCADE
    )

    mail_to_group = models.ManyToManyField(
        Group, verbose_name=_('Notification to'),
        blank=True,
        help_text=_('If user successfuly completed registration.<br/>'
            'Notification would be sent to users from selected groups<br/>'
            'Leave blank to disable notifications.<br/>'))

    def copy_relations(self, oldinstance):
        self.mail_to_group.set(oldinstance.mail_to_group.all())
