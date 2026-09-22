PYTHON ?= python

.PHONY: verify
verify:
	$(PYTHON) manage.py check
	$(PYTHON) manage.py makemigrations --check --dry-run
	$(PYTHON) manage.py migrate --noinput
	$(PYTHON) manage.py collectstatic --noinput
	$(PYTHON) manage.py test -v 2
