PYTHON ?= python

.PHONY: install test marketing ecommerce macro all

install:
	$(PYTHON) -m pip install -r requirements.txt

test:
	$(PYTHON) -m pytest -q

marketing:
	$(PYTHON) projects/01_marketing_analytics/run.py

ecommerce:
	$(PYTHON) projects/02_ecommerce_analytics/run.py

macro:
	$(PYTHON) projects/03_cis_macro_analytics/run.py

all: marketing ecommerce macro
