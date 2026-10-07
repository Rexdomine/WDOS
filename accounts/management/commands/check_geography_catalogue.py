from django.core.management.base import BaseCommand, CommandError
from accounts.geography_catalogue import check_geography_completeness


class Command(BaseCommand):
    help = "Run a country-by-country completeness check on the WDOS geography catalogue."

    def add_arguments(self, parser):
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Only print summary and failures.",
        )

    def handle(self, *args, **options):
        quiet = options.get("quiet", False)
        self.stdout.write(self.style.NOTICE("Running WDOS geography catalogue completeness check...\n"))

        result = check_geography_completeness()
        country_reports = result["country_reports"]

        header = f"{'Country':<32} {'ISO3':<5} {'ISO2':<5} {'Level 1':<8} {'Level 2':<8} {'Reliable':<9} {'Status':<6} {'Source'}"
        self.stdout.write(header)
        self.stdout.write("-" * len(header) + "-" * 20)

        for rep in country_reports:
            if quiet and rep["status"] == "PASS":
                continue
            line = (
                f"{rep['name']:<32} "
                f"{rep['iso3']:<5} "
                f"{rep['iso2']:<5} "
                f"{rep['level1_count']:<8} "
                f"{rep['level2_count']:<8} "
                f"{('Yes' if rep['level2_reliable'] else 'No'):<9} "
                f"{(self.style.SUCCESS('PASS') if rep['status'] == 'PASS' else self.style.ERROR('FAIL')):<6} "
                f"{rep['source']} ({rep['source_version']})"
            )
            self.stdout.write(line)
            if rep["errors"]:
                for err in rep["errors"]:
                    self.stdout.write(self.style.ERROR(f"    - Error: {err}"))

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(f"Total Countries Checked: {result['country_count']}/55")
        self.stdout.write(f"Total Level 1 Divisions: {result['total_level1']}")
        self.stdout.write(f"Total Level 2 Divisions: {result['total_level2']}")
        self.stdout.write(f"Validation Errors:      {len(result['errors'])}")
        self.stdout.write("=" * 60)

        if not result["valid"]:
            raise CommandError(
                f"Completeness check failed with {len(result['errors'])} error(s). "
                f"Catalogue must be complete before release."
            )

        self.stdout.write(self.style.SUCCESS("\nALL 55 AFRICAN COUNTRIES PASSED GEOGRAPHY COMPLETENESS CHECK."))
