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
TASK_STATE_NAMES = ("Inbox", "Active", "Finished", "Closed")
TASK_STATE_VERBS = {
    (0, 1): ("Accept", "arrow-down"),
    (0, 2): ("Finish", "ok"),
    (0, 3, True): ("Reject", "remove"), # asignee sees if the task is not self-assigned
    (0, 3): ("Close", "ok"), # assignee sees this for anonymously assigned tasks only
    (1, 0): ("Move to Inbox", "envelope"),
    (1, 2): ("Finish", "ok"),
    (1, 3): ("Close", "ok"),
    (2, 0): ("Move to Inbox", "envelope"),
    (2, 1): ("Return to Active", "repeat"),
    (2, 3): ("Close", "ok"),
    (3, 0): ("Move to Inbox", "envelope"),
    (3, 1): ("Return to Active", "repeat"),
    (3, 2): ("Return to Finished", "backward"),

    (0, "DELETE"): ("Delete", "remove"), # assigner sees if not self-assigned
    (1, "DELETE"): ("Delete", "remove"),
    (2, "DELETE"): ("Delete", "remove"),
    (3, "DELETE"): ("Delete", "remove"),
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

    def title_for_assigned_to(self):
        # How should we display the title of this list in outgoing
        # tasks lists? If the list is owned by a single user and that
        # user has just one list, display the owner's username. Otherwise
        # display the title of this list.
        if self.owners.count() == 1:
            owner = self.owners.first()
            if owner.tasklists_owned.count() <= 1:
                return str(owner)
        return self.title

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

    def __str__(self):
        return \
            self.created.isoformat() \
            + " " \
            + (self.outgoing.title_for_assigned_to() if self.outgoing else "Anonymous") \
            + " => " \
            + self.incoming.title_for_assigned_to() \
            + ": " + self.title

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
        if incoming == outgoing:
            # Self-assigned tasks start in the Active state.
            t.state = 1
        else:
            # Put the task in the inbox.
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

    def was_rejected(self):
        return isinstance(self.metadata, dict) and (self.metadata.get("rejected") == True)

    def new_dependency(self, user, incoming):
        """Creates a new dependency for the Task posted to another TaskList."""
        return Task.new(user, self.incoming, incoming, self)

    def add_state_matrix_for(self, user):
        self.state_matrix = []
        for transition in self.get_state_matrix(user):
            verb = TASK_STATE_VERBS[transition]
            self.state_matrix.append( (transition[0], transition[1], verb) )

    def get_state_matrix(self, user):
        """Which states can this user change the state of this task to?
        Note that he might be an owner of both the outgoing and incoming tasklists.
        Here we prevent transitions directly between 0/1 and 3, which may or may not be desirable."""
        in_roles = self.incoming.get_user_roles(user)
        out_roles = self.outgoing.get_user_roles(user) if self.outgoing else set() # might be an anonymous task
        ret = set()
        if "admin" in in_roles:
            # An admin on the incoming list can move a task between states 0 (inbox), 1 (active),
            # and 2 (finished). If the user is also an admin on the outgoing list, then instead
            # of finishing the task, he can close it instead. A user can also move a new task
            # directly to close to reject it.
            for s1 in (0, 1, 2):
                for s2 in (0, 1, 2):
                    if s1 == s2: continue
                    if "admin" in out_roles and s2 == 0:
                        # self-assigned tasks cannot be moved to the inbox
                        continue
                    elif ("admin" in out_roles or self.creator is None) and s2 == 2:
                        # self-assigned and anonymous tasks get closed instead of finished
                        if "admin" in out_roles and s1 == 0: continue # self-assigned tasks are never in state 0
                        ret.add((s1, 3))
                    else:
                        ret.add((s1, s2))
            if "admin" not in out_roles:
                # task is not self-assigned
                ret.add((0, 3, True)) # reject
                ret.add((3, 0)) # un-reject
            else:
                # this is a self-assigned task
                for s1 in (1, 2, 3):
                    ret.add((s1, "DELETE")) # can delete at any time (self-assigned tasks are never in state 0)


        if "admin" in out_roles:
            # An admin on the outgoing list can move a task between 2 (finished) and 3 (closed).
            # If the user is also an admin on the incoming list, in which case he wasn't given
            # the 'finished' option, then instead of moving from closed to finished move from
            # closed to active.
            ret.add((2, 3))
            if "admin" not in in_roles:
                # task is not self-assigend
                if not self.was_rejected():
                    # once a task is rejected, the asigner can't un-reject it
                    ret.add((3, 2))
                ret.add((0, "DELETE")) # can delete only when the assignee has not yet acknowledged it
            else:
                ret.add((3, 1))
        return sorted(s for s in ret if s != self.state)

    def change_state(self, user, new_state):
        """Changes the state of a task. The incoming owners can move a
        Task between Inbox, Active, and Finished, and the outgoing owner can
        move a Task between Finished to Closed. The creator of a Task has
        no special permission if he isn't an owner of either. To reject
        a task's outcome, the outgoing owner should close and start a new
        task."""

        # TODO: This method needs some locking/synchronization.

        if self.state == new_state: return

        # check permissions
        is_rejection = False
        if user:
            for transition in self.get_state_matrix(user):
                if transition[0] == self.state and transition[1] == new_state:
                    # This is permitted.

                    # Check if this is a transition that marks the task as rejected.
                    if len(transition) == 3: is_rejection = transition[2]

                    break # flag that we've found the permitted transition
            else:
                # This is not permitted.
                raise ValueError("You do not have permission to make that change.")

        if new_state == "DELETE":
            # This is a hard delete of a task.
            self.delete()
            return

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

        # was this a rejection?
        if is_rejection:
            m = self.metadata
            if not m: m = { }
            m["rejected"] = True
            self.metadata = m
        elif self.was_rejected():
            m = self.metadata
            del m["rejected"]
            self.metadata = m

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
