# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse
from django.http import Http404, HttpResponsePermanentRedirect
from django.shortcuts import redirect, render
from django.db import transaction
from django.contrib import messages
from django.contrib.auth.models import User
from django.utils.translation import (
    ugettext as _, get_language_from_request
)

from django.views.generic import CreateView, DetailView, ListView, TemplateView, View
from django.views.generic.base import TemplateResponseMixin

from aldryn_apphooks_config.mixins import AppConfigMixin
from aldryn_apphooks_config.utils import get_app_instance
from menus.utils import set_language_changer
from parler.views import TranslatableSlugMixin
from emailit.api import send_mail


from .forms import (
    JobApplicationForm,
    NewsletterConfirmationForm,
    NewsletterSignupForm,
    NewsletterUnsubscriptionForm,
    NewsletterResendConfirmationForm
)
from .models import (
    JobCategory,
    JobOpening,
    NewsletterSignup,
    NewsletterSignupUser,
    JobsConfig
)
from pardot.api import Pardot


class JobsBaseMixin(object):
    template_name = 'aldryn_jobs/jobs_list.html'
    model = JobOpening

    def dispatch(self, request, *args, **kwargs):
        # prepare language for misc usage
        self.language = get_language_from_request(request, check_path=True)
        return super(JobsBaseMixin, self).dispatch(request, *args, **kwargs)

    def get_queryset(self):
        """
        Base queryset returns active JobOpenings with respect to language and
        namespace. selects related categories, no ordering.
        """
        # if config is none - probably apphook relaod is in progress, or
        # something is wrong, anyway do not fail with 500
        if self.config is None:
            return JobOpening.objects.none()
        return (
            JobOpening.objects.active()
                              .namespace(self.config.namespace)
                              .language(self.language)
                              .active_translations(self.language)
                              .select_related('category')
        )


class JobOpeningList(JobsBaseMixin, AppConfigMixin, ListView):

    def get_queryset(self):
        return super(JobOpeningList, self).get_queryset().order_by(
            'country', 'category__ordering', 'ordering')


class CategoryJobOpeningList(JobsBaseMixin, AppConfigMixin, ListView):
    def get_queryset(self):
        category_slug = self.kwargs['category_slug']
        try:
            self.category = (
                JobCategory.objects
                           .language(self.language)
                           .active_translations(self.language,
                                                slug=category_slug)
                           .namespace(self.namespace)
                           .get()
            )
        except JobCategory.DoesNotExist:
            raise Http404

        self.set_language_changer(category=self.category)
        return (super(CategoryJobOpeningList, self).get_queryset()
                .filter(category=self.category)
                .order_by('ordering'))

    def set_language_changer(self, category):
        """Translate the slug while changing the language."""
        set_language_changer(self.request, category.get_absolute_url)


class JobOpeningDetail(AppConfigMixin, TranslatableSlugMixin, DetailView):
    model = JobOpening
    form_class = JobApplicationForm
    template_name = 'aldryn_jobs/jobs_detail.html'
    slug_url_kwarg = 'job_opening_slug'

    def dispatch(self, request, *args, **kwargs):
        self.request = request
        self.namespace, self.config = get_app_instance(request)
        self.object = self.get_object()
        self.set_language_changer(self.object)
        return super(JobOpeningDetail, self).dispatch(request, *args, **kwargs)

    def get_form_class(self):
        return self.form_class

    def get_form_kwargs(self):
        """
        Returns the keyword arguments for instantiating the form.
        """
        kwargs = {'job_opening': self.object}

        if self.request.method in ('POST', 'PUT'):
            kwargs.update({
                'data': self.request.POST,
                'files': self.request.FILES,
            })
        return kwargs

    def get_form(self, form_class):
        """
        Returns an instance of the form to be used in this view.
        """
        return form_class(**self.get_form_kwargs())

    def set_language_changer(self, job_opening):
        """Translate the slug while changing the language."""
        set_language_changer(self.request, job_opening.get_absolute_url)

    def get(self, *args, **kwargs):
        form_class = self.get_form_class()
        self.form = self.get_form(form_class)
        return super(JobOpeningDetail, self).get(*args, **kwargs)

    def get_queryset(self):
        qs = super(JobOpeningDetail, self).get_queryset()
        return qs.namespace(self.namespace)

    @transaction.atomic
    def post(self, *args, **kwargs):
        """Handles application for the job."""
        if not self.object.can_apply:
            messages.success(self.request, _("You can't apply for this job."))
            return redirect(self.object.get_absolute_url())

        form_class = self.get_form_class()
        self.form = self.get_form(form_class)

        if self.form.is_valid():
            self.form.save()
            msg = _("You have successfully applied for %(job)s.") % {
                'job': self.object.title
            }
            messages.success(self.request, msg)
            return redirect(self.object.get_absolute_url())
        else:
            return super(JobOpeningDetail, self).get(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(JobOpeningDetail, self).get_context_data(**kwargs)
        context['form'] = self.form
        return context


class ConfirmNewsletterSignup(TemplateResponseMixin, View):
    http_method_names = ["get", "post"]
    messages = {
        "key_confirmed": {
            "level": messages.SUCCESS,
            "text": _("You have confirmed {email}.")
        }
    }
    form_class = NewsletterConfirmationForm

    def get_template_names(self):
        return {
            "GET": ["aldryn_jobs/newsletter/confirm.html"],
            "POST": ["aldryn_jobs/newsletter/confirmed.html"],
        }[self.request.method]

    def get(self, *args, **kwargs):
        self.object = self.get_object()
        # if recipient already confirmed his email then there is
        # a high chance that this is a brute force attack
        if self.object.is_verified and not self.object.is_disabled:
            raise Http404()
        ctx = self.get_context_data()
        # populate form with key
        form_class = self.get_form_class()
        ctx['form'] = form_class(
            initial={'confirmation_key': self.kwargs['key']})
        return self.render_to_response(ctx)

    def post(self, *args, **kwargs):
        form_class = self.get_form_class()
        form_confirmation_key = self.request.POST.get('confirmation_key')
        # since we using a form and have a unique constraint on confirmation
        # key we need to get instance before validating the form
        try:
            instance = NewsletterSignup.objects.get(
                confirmation_key=form_confirmation_key,
                is_verified=False)
        except NewsletterSignup.DoesNotExist:
            raise Http404()
        form = form_class(self.request.POST, instance=instance)
        if form.is_valid():
            self.object = instance
            # do not confirm second time
            if not self.object.is_verified:
                self.object.confirm()
                self.after_confirmation(self.object)
        else:
            # be careful if you add custom fields on confirmation form
            # validate errors will cause a 404.
            raise Http404()

        redirect_url = self.get_redirect_url()
        if not redirect_url:
            ctx = self.get_context_data()
            return self.render_to_response(ctx)

        if self.messages.get("key_confirmed"):
            messages.add_message(
                self.request,
                self.messages["key_confirmed"]["level"],
                self.messages["key_confirmed"]["text"].format(**{
                    "email": self.object.recipient
                })
            )
        return redirect(redirect_url)

    def get_object(self, queryset=None):
        if queryset is None:
            queryset = self.get_queryset()
        try:
            return queryset.filter(
                confirmation_key=self.kwargs["key"])[:1].get()
            # Until the model-field is not set to unique=True,
            # we'll use the trick above
        except NewsletterSignup.DoesNotExist:
            raise Http404()

    def get_queryset(self):
        qs = NewsletterSignup.objects.all()
        return qs

    def get_context_data(self, **kwargs):
        ctx = kwargs
        ctx["confirmation"] = self.object
        return ctx

    def get_form_class(self):
        return self.form_class

    def get_redirect_url(self):
        """ Implement this for custom redirects """
        return None

    def after_confirmation(self, signup):
        """ Implement this for custom post-save operations """
        # eventually we don't have abilities right now to track which plugin
        # was used to register for newsletter, so we will use all matching
        # plugins with filtering by language and app_config
        plugins_base_qs = signup.app_config.jobnewsletterregistrationplugin_set.filter(  # NOQA
            language=signup.default_language)
        # also do not use draft settings, only plugins from public pages
        # plugin page.pk should match page.get_public_object().pk
        page_public_plugins = [plugin for plugin in plugins_base_qs if plugin.page and (
            plugin.page.get_public_object() and plugin.page.pk == plugin.page.get_public_object().pk
        )]
        static_public_plugins = [plugin for plugin in plugins_base_qs if plugin.placeholder.static_public.exists()]
        public_plugins = page_public_plugins or static_public_plugins

        public_plugins_groups = set(
            [group for plugin in
                public_plugins
             for group in plugin.mail_to_group.all()]
        )
        # eventually get emails of users from matching groups
        admin_recipients = set(
            [user.email for group in public_plugins_groups
                for user in group.user_set.all()])

        # if we have something special from settings - also use those lists
        # of addresses to notify about successful user registration
        additional_recipients = getattr(
            settings, 'ALDRYN_JOBS_NEWSLETTER_ADDITIONAL_NOTIFICATION_EMAILS',
            [])
        additional_recipients += getattr(
            settings, 'ALDRYN_JOBS_DEFAULT_SEND_TO', [])

        if additional_recipients:
            admin_recipients.update(additional_recipients)

        context = {
            'new_recipient': signup.recipient
        }
        for admin_recipient in admin_recipients:
            send_mail(
                recipients=[admin_recipient],
                context=context,
                template_base='aldryn_jobs/emails/newsletter_new_recipient')


class UnsubscibeNewsletterSignup(TemplateResponseMixin, View):
    http_method_names = ["get", "post"]
    form_class = NewsletterUnsubscriptionForm

    def get_template_names(self):
        return {
            "GET": ["aldryn_jobs/newsletter/unsubscribe.html"],
            "POST": ["aldryn_jobs/newsletter/unsubscribed.html"],
        }[self.request.method]

    def get(self, *args, **kwargs):
        self.object = self.get_object()
        # if object is disabled - do not serve this page
        if self.object.is_disabled or not self.object.is_verified:
            raise Http404()
        ctx = self.get_context_data()
        # populate form with key
        form_class = self.get_form_class()
        ctx['form'] = form_class(
            initial={'confirmation_key': self.kwargs['key']})
        return self.render_to_response(ctx)

    def post(self, *args, **kwargs):
        form_confirmation_key = self.request.POST.get('confirmation_key')
        # since we using a form and have a unique constraint on confirmation
        # key we need to get instance before validating the form
        try:
            instance = NewsletterSignup.objects.active_recipients().get(
                confirmation_key=form_confirmation_key)
        except NewsletterSignup.DoesNotExist:
            raise Http404()

        form_class = self.get_form_class()
        form = form_class(self.request.POST, instance=instance)

        if form.is_valid():
            self.object = instance
            # do not confirm second time
            if not self.object.is_disabled:
                self.object.disable()
                # run custom actions, if there is
                self.after_unsubscription(self.object)
        else:
            # be careful if you add custom fields on confirmation form
            # validate errors will cause a 404.
            raise Http404()

        redirect_url = self.get_redirect_url()
        if not redirect_url:
            ctx = self.get_context_data()
            return self.render_to_response(ctx)

        return redirect(redirect_url)

    # for flexibility
    def get_object(self, queryset=None):
        if queryset is None:
            queryset = self.get_queryset()
        try:
            return queryset.get(confirmation_key=self.kwargs["key"])
        except NewsletterSignup.DoesNotExist:
            raise Http404()

    def get_queryset(self):
        qs = NewsletterSignup.objects.all()
        return qs

    def get_context_data(self, **kwargs):
        ctx = kwargs
        ctx["confirmation"] = self.object
        return ctx

    def get_form_class(self):
        return self.form_class

    def get_redirect_url(self):
        """ Implement this for custom redirects """
        return None

    def after_unsubscription(self, signup):
        """ Implement this for custom post-save operations """
        # raise NotImplementedError()
        pass


class RegisterJobNewsletter(CreateView):
    form_class = NewsletterSignupForm

    def dispatch(self, request, *args, **kwargs):
        namespace = ''
        resolver_match = getattr(self.request, 'resolver_match', None)
        if resolver_match is not None:
            namespace = getattr(resolver_match, 'namespace', '')

        if len(namespace) < 1:
            if (self.request.current_page and self.request.current_page.application_namespace):
                namespace = self.request.current_page.application_namespace

        if len(namespace) < 1:
            raise ImproperlyConfigured(
                "Cant find name space, please either fix it "
                "or enable cms CurrentPage middleware")
        # in memory thing, we need it for form processing etc.
        # FIXME: unfortunately app config namespace is not unique,
        # using only first match
        app_config = JobsConfig.objects.filter(namespace=namespace)
        if app_config:
            app_config = app_config[0]
        self.app_config = app_config

        return super(RegisterJobNewsletter, self).dispatch(request,
                                                           *args, **kwargs)

    def get(self, request, *args, **kwargs):
        # TODO: add GET requests registration functionality
        # don't serve get requests, only plugin registration so far
        return HttpResponsePermanentRedirect(
            reverse('{0}:job-opening-list'.format(self.app_config.namespace)))

    def get_invalid_template_name(self):
        return 'aldryn_jobs/newsletter/invalid_email.html'

    def get_form_kwargs(self):
        kwargs = super(RegisterJobNewsletter, self).get_form_kwargs()
        kwargs.update({'app_config': self.app_config})
        return kwargs

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.confirmation_key = NewsletterSignup.objects.generate_random_key()

        # try to get language
        if getattr(self.request, 'LANGUAGE_CODE', None) is not None:
            self.object.default_language = self.request.LANGUAGE_CODE
        else:
            self.object.default_language = get_language_from_request(
                self.request, check_path=True)

        # populate object with other data
        self.object.app_config = self.app_config
        if self.request.user.is_authenticated:
            user = self.request.user
        else:
            user = None
        if user is not None:
            # in memory only property, will be used just for confirmation email
            self.object.user = user
        self.object.save()

        if user:
            NewsletterSignupUser.objects.create(
                signup=self.object, user=user)
        self.object.send_newsletter_confirmation_email(request=self.request)
        try:
            self.update_pardot_prospect(self.object)
        except:
            pass
        return super(RegisterJobNewsletter, self).form_valid(form)

    def update_pardot_prospect(self, signup):
        pardot = Pardot()
        pardot.newsletter_signup_by_email(signup.recipient)

    def form_invalid(self, form):
        context = self.get_context_data()
        context['app_config'] = self.app_config
        # check if user needs a resend confirmation link
        recipient_email = form.data.get('recipient')
        recipient_object = NewsletterSignup.objects.filter(
            recipient=recipient_email)
        # check for registered but not confirmed
        context['resend_confirmation'] = None
        context['condition'] = None
        if recipient_email is not None and recipient_object:
            recipient_object = recipient_object[0]
            if recipient_object.is_disabled:
                context['condition'] = 'disabled'
            elif not recipient_object.is_verified:
                context['condition'] = 'not_confirmed'
            elif recipient_object.is_verified:
                context['condition'] = 'confirmed'
            context['resend_confirmation'] = reverse(
                '{0}:resend_confirmation_link'.format(
                    self.app_config.namespace),
                kwargs={'key': recipient_object.confirmation_key})
        template_name = self.template_invalid_name if (
            hasattr(self, 'template_invalid_name')) else (
            self.get_invalid_template_name())
        return render(self.request, template_name, context)

    def get_success_url(self):
        return reverse('{0}:newsletter_registration_notification'.format(self.app_config.namespace))


class ResendNewsletterConfirmation(ConfirmNewsletterSignup):
    form_class = NewsletterResendConfirmationForm

    def get_template_names(self):
        return {
            "GET": ["aldryn_jobs/newsletter/resend_confirmation.html"],
            "POST": ["aldryn_jobs/newsletter/confirmation_resent.html"],
        }[self.request.method]

    def post(self, *args, **kwargs):
        form_confirmation_key = self.request.POST.get('confirmation_key')
        try:
            self.object = NewsletterSignup.objects.get(
                confirmation_key=form_confirmation_key)
        except NewsletterSignup.DoesNotExist:
            raise Http404()
        form_class = self.get_form_class()
        form = form_class(self.request.POST, instance=self.object)

        if form.is_valid():
            self.object.reset_confirmation()

        redirect_url = self.get_redirect_url()
        if not redirect_url:
            ctx = self.get_context_data()
            return self.render_to_response(ctx)

        return redirect(redirect_url)


class SuccessRegistrationMessage(TemplateView):
    template_name = 'aldryn_jobs/newsletter/registered.html'
