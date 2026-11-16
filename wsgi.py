import importlib.util
import os

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("barbearia_main", os.path.join(ROOT_DIR, "app.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

app = module.app