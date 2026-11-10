"""Run Django/unittest cases under branch coverage and emit an auditable summary."""
import io
import json
import os
import sys
from pathlib import Path
import coverage

HERE=Path(__file__).resolve().parent
os.chdir(HERE)
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
cov=coverage.Coverage(config_file=str(HERE/'.coveragerc'))
cov.start()
import django
django.setup()
from django.test.runner import DiscoverRunner
stream=io.StringIO()

class RecordingRunner(DiscoverRunner):
    def run_suite(self,suite,**kwargs):
        import unittest
        result=unittest.TextTestRunner(verbosity=2,stream=stream).run(suite)
        self.result=result
        return result

runner=RecordingRunner(verbosity=1,interactive=False)
failures=runner.run_tests(['blog.tests'])
cov.stop();cov.save()
output=HERE.parent/'evidence';output.mkdir(exist_ok=True)
total=cov.html_report()
cov.json_report(outfile=str(output/'coverage.json'))
report=stream.getvalue();print(report)
(output/'python-tests.txt').write_text(report,encoding='utf-8')
(output/'test-summary.json').write_text(json.dumps({'tests':runner.result.testsRun,'failures':len(runner.result.failures),'errors':len(runner.result.errors),'coverage_percent':round(total,2)},indent=2),encoding='utf-8')
cov.report()
sys.exit(bool(failures))
