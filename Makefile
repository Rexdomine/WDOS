PYTHON ?= python

.PHONY: verify
verify:
	$(PYTHON) manage.py check
	$(PYTHON) manage.py makemigrations --check --dry-run
	$(PYTHON) manage.py migrate --noinput
	$(PYTHON) manage.py collectstatic --noinput
	$(PYTHON) manage.py test accounts.test_migrations foundation.test_stage10_multilingua.Stage10MultilinguaAndEventsTestSuite.test_live_transcript_persistence_and_mtg05_bridge -v 2
