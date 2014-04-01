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
	# Which tasklist(s) are we to display?
	if not slug:
		# a list must be given in the URL for non-authenticated users
		if not request.user.is_authenticated():
			raise Http404()

		# otherwise, no slug means all of my lists
		tasklists = TaskList.objects.filter(owners=request.user)
		roles = set(["admin", "post", "observe"])
	else:
		# view a particular task list, if permissions allow it
		tl = get_object_or_404(TaskList, slug=slug)
		if len(tl.get_user_roles(request.user)) == 0: return HttpResponseForbidden()
		tasklists = [tl]
		roles = tl.get_user_roles(request.user)

	# Which tasks can the user view?
	tasks = Task.objects.all()
	if which_way == None: which_way = "incoming" # default view

	if which_way == "incoming":
		# What tasks have been assigned to this list?
		tasks = tasks.filter(incoming__in=tasklists)

		# If the user doesn't have permission to see what's on the list,
		# he can only see tasks that were created by him.
		if "observe" not in roles:
			# this user can only see what *he* has posted to the list
			if not request.user.is_authenticated():
				tasks = tasks.none() # nothing to see
			else:
				tasks = tasks.filter(creator=request.user)

	elif which_way == "outgoing":
		tasks = tasks.filter(outgoing__in=tasklists).exclude(incoming__in=tasklists)

		# If the user doesn't own the list, he can only see tasks that
		# were assigned to him.
		if "admin" not in roles:
			# this user can only see what *he* has posted to the list
			if not request.user.is_authenticated():
				return HttpResponseForbidden()
			else:
				tasks = tasks.filter(incoming__owners=request.user)

	else:
		raise ValueError(which_way)

	# Prepare tasks for rendering.
	tasks = tasks.order_by('-created')
	for task in tasks:
		prepare_for_view(task, request)

	# Group tasks by current state.
	task_groups = [
		(i, TASK_STATE_NAMES[i], [t for t in tasks if t.state == i])
		for i in range(len(TASK_STATE_NAMES))
	]

	# Are we looking at a single list?
	singleton_list = tasklists[0] if len(tasklists) == 1 else None

	return TemplateResponse(request, 'tasklist.html', {
		"singleton_list": singleton_list,
		"all_lists": tasklists if len(tasklists) > 1 else None,
		"baseurl": "/tasks" if slug in (None, "") else "/t/" + slug,
		"incoming_outgoing": which_way,
		"task_groups": task_groups,
		"roles": roles,
		"can_post_task": (which_way == "incoming" and "post" in roles) or (which_way == "outgoing" and "admin" in roles),
		"no_tasks": not tasks.exists(),
		"my_lists": TaskList.objects.filter(owners=request.user) if request.user.is_authenticated() else TaskList.objects.none(), # for assigning tasks
		})

def prepare_for_view(task, request):
	# what states can this user move the task into
	task.add_state_matrix_for(request.user)

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

@json_response
def tasklist_post(request):
	# the "outgoing" (assigner) list
	if request.user.is_authenticated():
		outgoing = get_object_or_404(TaskList, id=request.POST.get("outgoing"))
		if "admin" not in outgoing.get_user_roles(request.user):
			return HttpResponseForbidden()
	else:
		# this is an anonymous task
		outgoing = None

	# the incoming (assignee) list
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
	if not request.user.is_authenticated():
		t.metadata = { "owner_email": request.POST.get("assigner_email") }
	t.save()

	# render the task for the response
	from django.template import Context, Template, loader as template_loader
	prepare_for_view(t, request)
	template = template_loader.get_template("task.html")
	task_html = template.render(Context({
		"task": t,
		"user": request.user,
		"incoming_outgoing": request.POST.get("view_orientation"),
	}))

	return { "status": "ok", "task_html": task_html, "state": t.state, "is_self_task": (incoming == outgoing) }

@login_required
def profile_view(request):
	return TemplateResponse(request, 'profile.html', { })

def login_view(request):
	return TemplateResponse(request, 'login.html', {})

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
