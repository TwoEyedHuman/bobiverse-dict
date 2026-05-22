.PHONY: build build-all validate manifest test clean install-boox

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

install-boox:
	@if [ -z "$(TARGET_BOOK)" ]; then echo "Error: TARGET_BOOK required. Usage: make install-boox TARGET_BOOK=1 BOOX_PATH=/path/to/dicts"; exit 1; fi
	@if [ -z "$(BOOX_PATH)" ]; then echo "Error: BOOX_PATH required. Usage: make install-boox TARGET_BOOK=1 BOOX_PATH=/path/to/dicts"; exit 1; fi
	cp dist/book-$(TARGET_BOOK)/bobiverse-book-$(TARGET_BOOK).stardict.zip "$(BOOX_PATH)/"
	@echo "Installed bobiverse-book-$(TARGET_BOOK).stardict.zip → $(BOOX_PATH)"
