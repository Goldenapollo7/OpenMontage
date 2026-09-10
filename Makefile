PYTHON ?= python3

.PHONY: setup setup-check install install-dev install-gpu test test-contracts lint clean preflight demo demo-list hyperframes-doctor hyperframes-warm

# ---- One-command setup ----

# The real work lives in scripts/setup.py so that Windows users get the exact
# same steps without needing `make` — or a shell that understands `&&`.
# `python scripts/setup.py` is the documented Windows path.
setup:
	@$(PYTHON) scripts/setup.py

# Diagnose the toolchain (Python/Node/npm/ffmpeg) without installing anything.
setup-check:
	@$(PYTHON) scripts/setup.py --check-only

# ---- Individual installs ----

install:
	$(PYTHON) -m pip install -r requirements.txt

install-dev:
	$(PYTHON) -m pip install -r requirements-dev.txt

install-gpu:
	$(PYTHON) -m pip install -r requirements-gpu.txt
	$(PYTHON) -m pip install diffusers transformers accelerate

# ---- Testing ----

test:
	$(PYTHON) -m pytest tests/ -v

test-contracts:
	$(PYTHON) -m pytest tests/contracts/ -v

# ---- Utilities ----

preflight:
	$(PYTHON) -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.provider_menu(), indent=2))"

hyperframes-doctor:
	@echo "==> Probing HyperFrames runtime (node/ffmpeg/npx + hyperframes doctor)..."
	$(PYTHON) -c "from tools.video.hyperframes_compose import HyperFramesCompose; r=HyperFramesCompose().execute({'operation':'doctor'}); import json; print(json.dumps(r.data, indent=2)); print('OK' if r.success else f'FAIL: {r.error}')"

hyperframes-warm:
	@echo "==> Refreshing the HyperFrames npx cache to latest..."
	@echo "    Uses --prefer-online so npx picks up new releases since your last run."
	npx --yes --prefer-online hyperframes --version
	@echo "==> Cache warm complete."

demo:
	@echo "==> Rendering zero-key demo videos (no API keys needed)..."
	@echo "    These use only Remotion components — animated charts, text, data viz."
	@echo ""
	$(PYTHON) render_demo.py

demo-list:
	@$(PYTHON) render_demo.py --list

lint:
	$(PYTHON) -m py_compile tools/base_tool.py
	$(PYTHON) -m py_compile tools/tool_registry.py
	$(PYTHON) -m py_compile tools/cost_tracker.py
	$(PYTHON) -m py_compile tools/analysis/composition_validator.py

clean:
	$(PYTHON) -c "import pathlib, shutil; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('__pycache__')]; [p.unlink() for p in pathlib.Path('.').rglob('*.pyc')]"
