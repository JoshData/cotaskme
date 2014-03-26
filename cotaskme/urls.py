from django.conf.urls import patterns, include, url

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    url(r'^$', 'cotaskme.views.home', name='home'),
    url(r'^new-task-list$', 'cotaskme.views.newlist', name='newlist'),

    url(r'^_search_for_recipient$', 'cotaskme.views.search_for_recipient'),

    url(r'^tasks()(?:/(outgoing|incoming))?$', 'cotaskme.views.tasklist', name='tasklist'),
    url(r'^t/([^/]+)$', 'cotaskme.views.tasklist', name='tasklist'),
    url(r'^_action$', 'cotaskme.views.tasklist_action', name='tasklist_action'),
    url(r'^_post$', 'cotaskme.views.tasklist_post', name='tasklist_post'),

    url('', include('social.apps.django_app.urls', namespace='social')),
    url('logout$', 'cotaskme.views.logout_view'),
    url('profile$', 'cotaskme.views.profile_view'),

    url(r'^admin/', include(admin.site.urls)),
)
