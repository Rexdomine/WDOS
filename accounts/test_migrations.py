from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class UpgradeTests(TransactionTestCase):
    def test_stage_one_user_and_roles_survive_additive_upgrade(self):
        # Only Django's disposable test DB is used; restore latest schema even on failure.
        executor=MigrationExecutor(connection)
        latest=executor.loader.graph.leaf_nodes()
        try:
            executor.migrate([('accounts',None)])
            user=get_user_model().objects.create_user(username='stage-one-existing',email='legacy@example.org',password='legacy test passphrase only')
            user_id=user.pk
            from foundation.models import Role
            from django.core.management import call_command
            from io import StringIO
            call_command('seed_roles',stdout=StringIO())
            roles=list(Role.objects.values_list('pk',flat=True))
            executor=MigrationExecutor(connection)
            executor.migrate(latest)
            self.assertTrue(get_user_model().objects.filter(pk=user_id,username='stage-one-existing').exists())
            self.assertEqual(list(Role.objects.values_list('pk',flat=True)),roles)
            from .models import Account
            self.assertFalse(Account.objects.filter(user_id=user_id).exists())
        finally:
            MigrationExecutor(connection).migrate(latest)
