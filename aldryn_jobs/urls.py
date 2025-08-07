# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from django.urls import re_path

from .views import (
    CategoryJobOpeningList,
    JobOpeningDetail,
    JobOpeningList,
    ConfirmNewsletterSignup,
    SuccessRegistrationMessage,
    RegisterJobNewsletter,
    UnsubscibeNewsletterSignup,
    ResendNewsletterConfirmation,
)

# default view (root url) which is pointing to ^$ url
DEFAULT_VIEW = 'job-opening-list'

urlpatterns = [
    re_path(r'^confirm-newsletter/$',
        RegisterJobNewsletter.as_view(),
        name="register_newsletter"),
    re_path(r'^confirm-newsletter/registration-notification/$',
        SuccessRegistrationMessage.as_view(),
        name="newsletter_registration_notification"),
    re_path(r'^confirm-newsletter/(?P<key>\w+)/$',
        ConfirmNewsletterSignup.as_view(),
        name="confirm_newsletter_email"),
    re_path(r'^unsubscribe-newsletter/(?P<key>\w+)/$',
        UnsubscibeNewsletterSignup.as_view(),
        name="unsubscribe_from_newsletter"),
    re_path(r'^resend-newsletter-confirmation/(?P<key>\w+)/$',
        ResendNewsletterConfirmation.as_view(),
        name="resend_confirmation_link"),
    re_path(r'^$', JobOpeningList.as_view(),
        name='job-opening-list'),
    re_path(r'^(?P<category_slug>\w[-_\w]*)/$',
        CategoryJobOpeningList.as_view(),
        name='category-job-opening-list'),
    re_path(r'^(?P<category_slug>\w[-_\w]*)/(?P<job_opening_slug>\w[-_\w]*)/$',
        JobOpeningDetail.as_view(),
        name='job-opening-detail'),
]
