#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.db import models
from django.contrib.auth.models import User

import random

from jsonfield import JSONField

TASK_LIST_AUTO_SLUG_LENGTH = 8
TASK_LIST_SLUG_MAX_LENGTH = 24
TASK_LIST_SLUG_AUTO_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
TASK_LIST_SLUG_OTHER_CHARS = "-_"
TASK_LIST_SLUG_CHARS = TASK_LIST_SLUG_AUTO_CHARS + TASK_LIST_SLUG_OTHER_CHARS
TASK_LIST_SLUG_CHAR_DESCRIPTION = "letters, numbers, dashes, and underscores"
TASK_STATE_NAMES = ("New", "Started", "Finished", "Closed")
TASK_STATE_VERBS = {
    (0, 1): ("Start", "play"),
    (0, 2): ("Finish", "ok"),
    (0, 3): ("Close", "ok"),
    (1, 0): ("Mark as New", "step-backward"),
    (1, 2): ("Finish", "ok"),
    (1, 3): ("Close", "ok"),
    (2, 0): ("Mark as New", "step-backward"),
    (2, 1): ("Return to Started", "asterisk"),
    (2, 3): ("Close", "ok"),
    (3, 0): ("Mark as New", "asterisk"),
    (3, 1): ("Return to Started", "step-backward"),
    (3, 2): ("Return to Finished", "backward"),
}

class TaskList(models.Model):
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    modified = models.DateTimeField(auto_now=True, db_index=True)
    slug = models.CharField(max_length=TASK_LIST_SLUG_MAX_LENGTH, db_index=True, unique=True)
    title = models.CharField(max_length=200)
    owners = models.ManyToManyField(User, db_index=True, related_name="tasklists_owned")
    posters = models.ManyToManyField(User, blank=True, db_index=True, related_name="tasklists_postable")
    observers = models.ManyToManyField(User, blank=True, db_index=True, related_name="tasklists_observed")
    public_to_post = models.BooleanField()
    public_to_observe = models.BooleanField()
    feeds_to = models.ManyToManyField('self', blank=True, db_index=True, related_name="feeds_from")
    notes = models.TextField(blank=True)
    metadata = JSONField()

    def get_absolute_url(self):
        return "/t/" + self.slug

    @staticmethod
    def new(owner):
        """Creates (and returns) a new TaskList owned by owner and with default settings."""
        tl = TaskList()
        tl.slug = "".join([random.choice(TASK_LIST_SLUG_CHARS) for i in range(TASK_LIST_AUTO_SLUG_LENGTH)])
        tl.title = TaskList.make_default_list_title(owner)
        tl.public_to_post = True
        tl.public_to_observe = False
        tl.notes = ""
        tl.save()
        tl.owners.add(owner)
        return tl

    @staticmethod
    def make_default_list_title(owner):
        return str(owner) + "'s Task List"

    def get_user_roles(self, user):
        """Returns whether the user has permission to administer, post to, or observe the contents of the TaskList."""
        if user in self.owners.all(): return set(["admin", "post", "observe"])
        ret = set()
        if self.public_to_post or user in self.posters.all():
            ret.add("post")
        if self.public_to_observe or user in self.observers.all():
            ret.add("observe")
        return ret

    def get_owners(self):
        return ", ".join( str(user) for user in self.owners.all() )

    def change_title(self, v):
        v = v.strip()
        if v == "":
            raise ValueError("You did not provide a new name.")
        self.title = v
        self.save()

    def change_slug(self, v):
        v = v.strip()
        if v == "":
            raise ValueError("You did not provide a new URL.")
        if len(v) > TASK_LIST_SLUG_MAX_LENGTH:
            raise ValueError("The new URL is too long.")
        for c in v:
            if c not in TASK_LIST_SLUG_CHARS:
                raise ValueError("The new URL may only contain %s." % TASK_LIST_SLUG_CHAR_DESCRIPTION)
        self.slug = v
        self.save()

class Task(models.Model):
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    modified = models.DateTimeField(auto_now=True, db_index=True)
    title = models.CharField(max_length=400)
    creator = models.ForeignKey(User, blank=True, null=True, db_index=True, related_name="tasks_created")
    notes = models.TextField(blank=True)
    outgoing = models.ForeignKey(TaskList, blank=True, null=True, db_index=True, related_name="tasks_outgoing", on_delete=models.PROTECT)
    incoming = models.ForeignKey(TaskList, db_index=True, related_name="tasks_incoming", on_delete=models.PROTECT)
    state = models.IntegerField(choices=enumerate(TASK_STATE_NAMES))
    hidden_on_outgoing = models.BooleanField(default=False)
    hidden_on_incoming = models.BooleanField(default=False)
    auto_close = models.BooleanField(default=False, help_text="Automatically close a task when it is finished.")
    dependencies = models.ManyToManyField('self', blank=True, db_index=True)
    auto_finish = models.BooleanField(default=False, help_text="Automatically finish a task when its dependencies are closed or finished.")
    metadata = JSONField()

    @staticmethod
    def new(user, outgoing, incoming, dependent=None):
        """Creates a new Task."""

        if outgoing and "admin" not in outgoing.get_user_roles(user): raise ValueError("User does not have permission to post an outgoing task on the outgoing task list.")
        if "post" not in incoming.get_user_roles(user): raise ValueError("User does not have permission to post a task on the incoming task list.")

        # TODO: validate information on anonymous tasks (outgoing=None)

        t = Task()
        t.title = "New Task" if not dependent else dependent.title
        t.creator = user if user.is_authenticated() else None
        t.notes = "" if not dependent else dependent.notes
        t.outgoing = outgoing
        t.incoming = incoming
        t.state = 0
        t.save()

        e = TaskEvent()
        e.task = t
        e.event_data = {
            "type": "created",
            "user": user.id if user.is_authenticated() else "anonymous",
            "outgoing": outgoing.id if outgoing else None,
            "incoming": incoming.id,
            "dependent": 0  if not dependent else dependent.id,
        }
        e.save()

        return t

    def new_dependency(self, user, incoming):
        """Creates a new dependency for the Task posted to another TaskList."""
        return Task.new(user, self.incoming, incoming, self)

    def add_state_matrix_for(self, user):
        self.state_matrix = []
        for old_state, new_state in self.get_state_matrix(user):
            self.state_matrix.append( (old_state, new_state, TASK_STATE_VERBS[(old_state, new_state)]) )

    def get_state_matrix(self, user):
        """Which states can this user change the state of this task to?
        Note that he might be an owner of both the outgoing and incoming tasklists.
        Here we prevent transitions directly between 0/1 and 3, which may or may not be desirable."""
        out_roles = self.incoming.get_user_roles(user)
        in_roles = self.outgoing.get_user_roles(user) if self.outgoing else set() # might be an anonymous task
        ret = set()
        if "admin" in out_roles:
            for s1 in (0, 1, 2):
                for s2 in (0, 1, 2):
                    if s1 == s2: continue
                    # if a user can both finish and close a task, give the option to close instead of finish
                    if "admin" in in_roles and s1 != 2 and s2 == 2: s2 = 3
                    ret.add((s1, s2))
        if "admin" in in_roles:
            for s1 in (2, 3):
                for s2 in (2, 3):
                    if s1 == s2: continue
                    # if a user can both finish and close a task, don't give the option to return to finish
                    if "admin" in out_roles and s1 == 3 and s2 == 2: s2 = 1
                    ret.add((s1, s2))
        return sorted(s for s in ret if s != self.state)

    def change_state(self, user, new_state):
        """Changes the state of a task. The incoming owners can move a
        Task between New, Started, and Finished, and the outgoing owner can
        move a Task between Finished to Closed. The creator of a Task has
        no special permission if he isn't an owner of either. To reject
        a task's outcome, the outgoing owner should close and start a new
        task."""

        # TODO: This method needs some locking/synchronization.

        if self.state == new_state: return

        # check permissions
        if user:
            out_roles = self.incoming.get_user_roles(user)
            in_roles = self.outgoing.get_user_roles(user) if self.outgoing else set() # might be an anonymous task
            if self.state in (0, 1, 2) and new_state in (0, 1, 2) and "admin" not in out_roles:
                raise ValueError("Only a user that this task is incoming for can make that state change.")
            if self.state in (2, 3) and new_state in (2, 3) and "admin" not in in_roles:
                raise ValueError("Only a user that this task is outgoing for can make that state change.")

        # record change
        e = TaskEvent()
        e.task = self
        e.event_data = {
            "type": "state",
            "user": user.id if user else None, # might be an automatic event
            "from": self.state,
            "to": new_state,
        }
        e.save()

        # make change
        self.state = new_state
        self.save()

        # if we're moving to the finished state and this Task is auto_close,
        # immediately close it.
        if new_state == 2 and self.auto_close:
            self.change_state(None, 3)
            return

        # If a dependent task has auto_finish and all its dependencies
        # are now finished or closed, finish that task too
        if new_state in (2, 3):
            for t in Task.objects.filter(dependencies=self, auto_finish=True, state__in=(0, 1)):
                t.check_autofinish(self)

    def check_autofinish(self, triggered_by):
        # Check that all dependencies are Finished or Closed, and if
        # so then Finish this Task too.
        #
        # TODO: Does this need locking/synchronization?
        if not self.auto_finish: raise ValueError("Not an auto_finish Task.")
        if self.state not in (0, 1): raise ValueError("Task is already Finished or Closed.")
        dep_states = self.dependencies.values_list("state", flat=True)
        for s in dep_states:
            if s not in (2, 3):
                return
        t.change_state(None, 2)


class TaskEvent(models.Model):
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    task = models.ForeignKey(Task, db_index=True, related_name="events")
    event_data = JSONField()

    def __str__(self):
        return str(self.event_data)

class UserHandle(models.Model):
    """A model just for searching for users by handle. Updated each time a user
    logs in with any handles on their associated social accounts."""
    user = models.ForeignKey(User, db_index=True, related_name="handles")
    handle = models.CharField(max_length=200, db_index=True)

    class Meta:
        unique_together = ('user', 'handle')

    @staticmethod
    def on_user_login(sender, user, request, **kwargs):
        # Get all of the handles on any social login accounts.
        from social.apps.django_app.default.models import UserSocialAuth
        handles = set()
        for usa in UserSocialAuth.objects.filter(user=user):
            if usa.provider == "google":
                handles.add( usa.uid ) # email address
            if usa.provider == "twitter":
                handles.add( usa.extra_data["access_token"]["screen_name"] )

        # Get existing handles for this user.
        old_handles = set(UserHandle.objects.filter(user=user).values_list('handle', flat=True))

        # Remove obsoleted records.
        if len(old_handles - handles) > 0:
            UserHandle.objects.filter(user=user, handle__in=(old_handles - handles)).delete()

        # Add new records.
        for h in handles - old_handles:
            UserHandle.objects.create(user=user, handle=h)

from django.contrib.auth.signals import user_logged_in
user_logged_in.connect(UserHandle.on_user_login)
