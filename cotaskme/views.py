from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden
from django.template.response import TemplateResponse
from django.contrib.auth.decorators import login_required

from cotaskme.models import TaskList, Task, TASK_STATE_NAMES
from cotaskme.utils import json_response

def home(request):
	return TemplateResponse(request, 'index.html', {
		"groups": TaskList.get_mine(request.user) if request.user.is_authenticated() else None
		})
	
@login_required
def newlist(request):
	tl = TaskList.new(request.user)
	return redirect(tl)

@login_required
def tasklist(request, slug):
	tl = get_object_or_404(TaskList, slug=slug)
	roles = tl.get_user_roles(request.user)
	if len(roles) == 0: return HttpResponseForbidden()

	my_incoming_lists = TaskList.objects.filter(owners=request.user)

	def build_tasks(qs):
		qs = qs.order_by('-created')
		tasks = list(qs)
		for task in tasks:
			task.next_states = [(s, TASK_STATE_NAMES[s]) for s in task.get_next_states(request.user)]
		return tasks

	tasks_incoming = build_tasks(tl.tasks_incoming.all())
	tasks_outgoing = build_tasks(tl.tasks_outgoing.all())

	return TemplateResponse(request, 'tasklist.html', {
		"tasklist": tl,
		"roles": roles,
		"my_incoming_lists": my_incoming_lists,
		"tasks_incoming": tasks_incoming,
		"tasks_outgoing": tasks_outgoing,
		})

@login_required
@json_response
def tasklist_action(request, slug):
	tl = get_object_or_404(TaskList, slug=slug)

	if request.POST.get("action") in ("rename", "slug"):
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
def tasklist_post(request, slug):
	tl = get_object_or_404(TaskList, slug=slug)
	if "post" not in tl.get_user_roles(request.user):
		return HttpResponseForbidden()

	if request.POST.get("incoming") in (None, ""):
		incoming = TaskList.new(request.user)
	else:
		incoming = get_object_or_404(TaskList, id=request.POST.get("incoming"))
		if "admin" not in tl.get_user_roles(request.user):
			return HttpResponseForbidden()

	# create the task
	t = Task.new(request.user, incoming, tl)

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