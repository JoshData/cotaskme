from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden
from django.template.response import TemplateResponse
from django.contrib.auth.decorators import login_required

import re

from cotaskme.models import TaskList, Task, TASK_STATE_NAMES
from cotaskme.utils import json_response

def template_context_processor(request):
	login_methods = []
	from social.apps.django_app.utils import BACKENDS
	from social.backends import utils
	icon_map = { "google": "googleplus" }
	return { "login_backends": [(name, icon_map.get(name, name)) for name in utils.load_backends(BACKENDS)] }

def home(request):
	if not request.user.is_authenticated():
		return TemplateResponse(request, 'index.html', { })
	else:
		tasklists = TaskList.objects.filter(owners=request.user)
		if tasklists.count() == 0:
			# redirect to a new task list
			return redirect(TaskList.new(request.user))
		elif tasklists.count() == 1:
			# redirect to the user's task list
			return redirect(tasklists[0])
		else:
			# redirect to the page that shows tasks on all lists
			return redirect("/tasks")
	
@login_required
def newlist(request):
	tl = TaskList.new(request.user)
	return redirect(tl)

def tasklist(request, slug=None, which_way=None):
	if not slug:
		# a list must be given in the URL for non-authenticated users
		if not request.user.is_authenticated():
			raise Http404()

		# otherwise, no slug means all of my lists
		tasklists = TaskList.objects.filter(owners=request.user)
	else:
		# view a particular task list, if permissions allow it
		tl = get_object_or_404(TaskList, slug=slug)
		if len(tl.get_user_roles(request.user)) == 0: return HttpResponseForbidden()
		tasklists = [tl]

	tasks = Task.objects.all()
	if which_way in ("incoming", None):
		tasks = tasks.filter(incoming__in=tasklists)
	elif which_way == "outgoing":
		tasks = tasks.filter(outgoing__in=tasklists).exclude(incoming__in=tasklists)

	tasks = tasks.order_by('-created')
	for task in tasks:
		# what states can this user move the task into (it depends on what list it came from)
		task.add_state_matrix_for(request.user)

	task_groups = [
		(i, TASK_STATE_NAMES[i], [t for t in tasks if t.state == i])
		for i in range(len(TASK_STATE_NAMES))
	]

	singleton_list = tasklists[0] if len(tasklists) == 1 else None

	return TemplateResponse(request, 'tasklist.html', {
		"singleton_list": singleton_list,
		"admin_list": singleton_list and "admin" in singleton_list.get_user_roles(request.user),
		"all_lists": tasklists if len(tasklists) > 1 else None,
		"baseurl": "/tasks" if slug in (None, "") else "/t/" + slug,
		"incoming_outgoing": which_way,
		"task_groups": task_groups,
		"no_tasks": not tasks.exists(),
		})

@login_required
@json_response
def tasklist_action(request):
	if request.POST.get("action") in ("rename", "slug"):
		tl = get_object_or_404(TaskList, slug=request.POST.get("slug"))
		if "admin" not in tl.get_user_roles(request.user):
			return HttpResponseForbidden()
			
		v = str(request.POST.get("value"))
		try:
			if request.POST.get("action") == "rename": tl.change_title(v)
			if request.POST.get("action") == "slug": tl.change_slug(v)
		except ValueError as e:
			return { "status": "error", "msg": str(e) }

	if request.POST.get("action") == "task-state":
		t = get_object_or_404(Task, id=request.POST.get("task"))
		try:
			t.change_state(request.user, int(request.POST.get("state")))
		except ValueError as e:
			return { "status": "error", "msg": str(e) }

	return { "status": "ok" }

@login_required
@json_response
def tasklist_post(request):
	outgoing = get_object_or_404(TaskList, id=request.POST.get("outgoing"))
	if "admin" not in outgoing.get_user_roles(request.user):
		return HttpResponseForbidden()

	m = re.match(r".* \[#(\d+)\]$", request.POST.get("incoming", ""))
	if m:
		incoming = get_object_or_404(TaskList, id=int(m.group(1)))
	else:
		try:
			id = int(request.POST.get("incoming"))
		except ValueError:
			return { "status": "error", "msg": "That is not a recipient we know." }
		incoming = get_object_or_404(TaskList, id=id)
		
	if "post" not in incoming.get_user_roles(request.user):
		return HttpResponseForbidden()

	# create the task
	t = Task.new(request.user, outgoing, incoming)

	# update with initial properties
	t.title = str(request.POST.get("title")).strip()
	t.notes = str(request.POST.get("note")).strip()
	t.save()

	# render the task for the response
	from django.template import Context, Template, loader as template_loader
	t.add_state_matrix_for(request.user)
	template = template_loader.get_template("task.html")
	task_html = template.render(Context({ "task": t, "user": request.user }))

	return { "status": "ok", "task_html": task_html, "state": t.state, "is_self_task": (incoming == outgoing) }

@login_required
def profile_view(request):
	return TemplateResponse(request, 'profile.html', { })

def logout_view(request):
	from django.contrib.auth import logout
	logout(request)
	return redirect("/")

@login_required
@json_response
def search_for_recipient(request):
	q = str(request.POST["query"])
	ret = []

	from cotaskme.models import UserHandle
	handles = UserHandle.objects.filter(handle__startswith=q).select_related("user")
	if len(handles) < 20:
		for h in handles:
			tasklists = list(TaskList.objects.filter(owners=h.user))
			tasklists = [tl for tl in tasklists if "post" in tl.get_user_roles(request.user)]
			for tl in tasklists:
				label = h.handle
				if len(tasklists) > 1: label += " - " + tl.title
				ret.append( {"value": label + " [#" + str(tl.id) + "]", "label": label })

	return ret
