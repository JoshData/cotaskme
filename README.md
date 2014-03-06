# CoTask.me

A task list where every task appears "incoming" on your list and "outgoing" on the task list of the person who requested the task.

Based on an idea by Matthew Burton at http://matthewburton.org/an-idea-for-to-do-lists/.

Built with Django 1.6. Works with either Python 2 or Python 3.

## Setup

	git submodule update --init
	virtualenv -p`which python3` .env
	. .env/bin/activate
	pip install -r pip-requirements.txt 
	mkdir db
	cp cotaskme/settings_local.py.tmpl cotaskme/settings_local.py # edit SECRET_KEY!
	./manage.py syncdb

## Run

	. .env/bin/activate
	./manage.py runserver

## When things change

	git submodule update --init
	. .env/bin/activate
	pip install -r pip-requirements.txt 
