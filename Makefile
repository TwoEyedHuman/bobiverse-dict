.PHONY: build build-all validate manifest test clean

PYTHON := uv run python

build:
	$(PYTHON) scripts/build.py --target-book all

build-all:
	$(PYTHON) scripts/build.py --all

validate:
	$(PYTHON) scripts/build.py --validate-only

manifest:
	$(PYTHON) scripts/build.py --manifest

test:
	uv run pytest

clean:
	rm -rf dist/
