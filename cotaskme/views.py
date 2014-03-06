from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden
from django.template.response import TemplateResponse
from django.contrib.auth.decorators import login_required

from cotaskme.models import TaskList, Task, TASK_STATE_VERBS
from cotaskme.utils import json_response

def home(request):
	if not request.user.is_authenticated():
		return TemplateResponse(request, 'index.html', { })
	else:
		return redirect("/tasks")
	
@login_required
def newlist(request):
	tl = TaskList.new(request.user)
	return redirect(tl)

def tasklist(request, slug=None, incoming_outgoing=None):
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
	if incoming_outgoing in ("outgoing", None):
		tasks = tasks.filter(outgoing__in=tasklists)
	elif incoming_outgoing == "incoming":
		tasks = tasks.filter(incoming__in=tasklists)

	tasks = tasks.order_by('-created')
	for task in tasks:
		# what states can this user move the task into (it depends on what list it came from)
		task.next_states = [(s, TASK_STATE_VERBS[(task.state, s)]) for s in task.get_next_states(request.user)]

	return TemplateResponse(request, 'tasklist.html', {
		"baseurl": "/tasks" if slug in (None, "") else "/" + slug,
		"incoming_outgoing": incoming_outgoing,
		"tasks": tasks,
		})

@login_required
@json_response
def tasklist_action(request):
	if request.POST.get("action") in ("rename", "slug"):
		tl = get_object_or_404(TaskList, slug=slug)
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
	if request.POST.get("incoming") == "_new":
		incoming = TaskList.new(request.user)
	elif request.POST.get("incoming") == "_default":
		tasklists = TaskList.objects.filter(owners=request.user)
		if len(tasklists) == 0:
			incoming = TaskList.new(request.user)
		else:
			# TODO: Better default?
			incoming = tasklists[0]
	else:
		incoming = get_object_or_404(TaskList, id=request.POST.get("incoming"))
		if "admin" not in tl.get_user_roles(request.user):
			return HttpResponseForbidden()

	if request.POST.get("outgoing") == "_not_impl":
		outgoing = incoming
	else:
		outgoing = get_object_or_404(TaskList, id=request.POST.get("outgoing"))
	if "post" not in outgoing.get_user_roles(request.user):
		return HttpResponseForbidden()

	# create the task
	t = Task.new(request.user, incoming, outgoing)

	# update with initial properties
	t.title = str(request.POST.get("title")).strip()
	t.notes = str(request.POST.get("note")).strip()
	t.autoclose = request.POST.get("autoclose") != None
	t.save()

	return { "status": "ok" }

def logout_view(request):
	from django.contrib.auth import logout
	logout(request)
	return redirect("/")