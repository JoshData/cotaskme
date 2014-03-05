from django.contrib import admin
from cotaskme.models import TaskList, Task, TaskEvent

admin.site.register(TaskList)
admin.site.register(Task)
admin.site.register(TaskEvent)
