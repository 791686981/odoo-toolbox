import importlib
import sys


def test_celery_app_imports_without_circular_dependency() -> None:
    for module_name in [
        "app.workers.celery_app",
        "app.tools.csv_translation",
        "app.tools.csv_translation.router",
    ]:
        sys.modules.pop(module_name, None)

    module = importlib.import_module("app.workers.celery_app")

    assert module.celery_app.main == "odoo_toolbox"
    assert module.run_translation_job.name == "csv_translation.run_translation_job"
