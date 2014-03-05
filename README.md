# CoTask.me

A task list where every task appears "outgoing" on your list and "incoming" on the task list of the person who requested the task.

Based on an idea by Matthew Burton at http://matthewburton.org/an-idea-for-to-do-lists/.

Built with Django 1.6 on Python 3.

## Setup

	virtualenv -p`which python3` .env
	. .env/bin/activate
	pip install -r pip-requirements.txt 
	mkdir db
	cp cotaskme/settings_local.py.tmpl cotaskme/settings_local.py # edit SECRET_KEY!
	./manage.py syncdb

## Run

	. .env/bin/activate
	./manage.py runserver
