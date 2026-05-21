.PHONY: build build-all validate test clean

PYTHON := uv run python

build:
	$(PYTHON) scripts/build.py --target-book all

build-all:
	$(PYTHON) scripts/build.py --all

validate:
	$(PYTHON) scripts/build.py --validate-only

test:
	uv run pytest

clean:
	rm -rf dist/
