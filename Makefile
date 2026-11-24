PYTHON ?= python
DOCKER_COMPOSE ?= docker compose

.PHONY: install test marketing ecommerce macro all docker-test docker-marketing docker-ecommerce docker-macro

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

docker-test:
	$(DOCKER_COMPOSE) run --build --rm tests

docker-marketing:
	$(DOCKER_COMPOSE) run --build --rm marketing

docker-ecommerce:
	$(DOCKER_COMPOSE) run --build --rm ecommerce

docker-macro:
	$(DOCKER_COMPOSE) run --build --rm macro
