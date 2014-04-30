from django.conf.urls import patterns, include, url

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    url(r'^$', 'cotaskme.views.home', name='home'),
    url(r'^new-task-list$', 'cotaskme.views.newlist', name='newlist'),

    url(r'^_search_for_recipient$', 'cotaskme.views.search_for_recipient'),

    url(r'^tasks()(?:/(outgoing|incoming))?$', 'cotaskme.views.tasklist', name='tasklist'),
    url(r'^t/([^/]+)(?:/(outgoing|incoming))?$', 'cotaskme.views.tasklist', name='tasklist'),
    url(r'^_action$', 'cotaskme.views.tasklist_action', name='tasklist_action'),
    url(r'^_post$', 'cotaskme.views.tasklist_post', name='tasklist_post'),
    url(r'^_claim$', 'cotaskme.views.new_user_claim_tasks', name='new_user_claim_tasks'),

    url('', include('social.apps.django_app.urls', namespace='social')),

    url('profile$', 'cotaskme.views.profile_view'),
    url('accounts/login/?$', 'cotaskme.views.login_view'),
    url('accounts/logout/?$', 'cotaskme.views.logout_view'),

    url(r'^admin/', include(admin.site.urls)),
)
