.PHONY: help up up-d down restart ps logs logs-odoo logs-db logs-odoo-file shell-odoo shell-db psql perms upgrade upgrade-all upgrade-all-debug restart-upgrade restart-upgrade-all wait-db wait-odoo ensure-up scaffold

# Load environment variables from .env if present
ifneq (,$(wildcard ./.env))
    include .env
    export
endif

COMPOSE ?= docker compose
PROJECT ?= odoo20-pos
CONTAINER ?= odoo20-pos-odoo20-1
DB_CONTAINER ?= odoo20-pos-db-1
DB_NAME ?= pos_saas_dev
DB_HOST ?= db
DB_USER ?= $(POSTGRES_USER)
DB_PASSWORD ?= $(POSTGRES_PASSWORD)
MODULE ?= point_of_sale

# Support: make upgrade <module_name> or make restart-upgrade <module_name>
ifneq (,$(filter upgrade restart-upgrade scaffold,$(firstword $(MAKECMDGOALS))))
ifneq (,$(word 2,$(MAKECMDGOALS)))
MODULE := $(word 2,$(MAKECMDGOALS))
define _DUMMY_TARGET
$1:
	@:
endef
$(eval $(call _DUMMY_TARGET,$(word 2,$(MAKECMDGOALS))))
endif
endif

help:
	@echo "=========================================================="
	@echo " Odoo 20 SaaS POS - Management Makefile"
	@echo "=========================================================="
	@echo "Targets:"
	@echo "  up                  Start containers in foreground"
	@echo "  up-d                Start containers in detached background"
	@echo "  down                Stop and remove containers"
	@echo "  restart             Restart all containers"
	@echo "  ps                  Show container status"
	@echo "  logs                Follow all logs"
	@echo "  logs-odoo           Follow Odoo 20 container logs"
	@echo "  logs-db             Follow Postgres logs"
	@echo "  logs-odoo-file      Tail log file in etc/odoo-server.log"
	@echo "  shell-odoo          Open bash in Odoo 20 container"
	@echo "  shell-db            Open bash in Postgres DB container"
	@echo "  psql                Open interactive psql CLI in DB container"
	@echo "  perms               Fix permissions for mounted folders (addons, etc, postgresql)"
	@echo "  scaffold <name>     Scaffold new Odoo module in addons/ (e.g. make scaffold pos_qris)"
	@echo "  upgrade <module>    Upgrade module (e.g. make upgrade point_of_sale)"
	@echo "  upgrade-all         Upgrade all installed modules (-u all)"
	@echo "  upgrade-all-debug   Upgrade all modules with verbose debug stdout logs"
	@echo "  restart-upgrade     Upgrade module then restart Odoo"
	@echo "  restart-upgrade-all Upgrade all modules then restart Odoo"
	@echo "  wait-db             Wait until PostgreSQL is healthy and ready"
	@echo "  wait-odoo           Wait until Odoo registry is loaded via HTTP check"
	@echo "=========================================================="

up:
	$(COMPOSE) up

up-d:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f --tail=200

logs-odoo:
	$(COMPOSE) logs -f --tail=200 odoo20

logs-db:
	$(COMPOSE) logs -f --tail=200 db

logs-odoo-file:
	@touch etc/odoo-server.log
	tail -f -n 200 etc/odoo-server.log

shell-odoo:
	$(COMPOSE) exec odoo20 bash

shell-db:
	$(COMPOSE) exec db bash

psql:
	$(COMPOSE) exec db psql -U $(DB_USER) -d $(DB_NAME)

perms:
	@echo "Fixing permissions for addons, etc, postgresql..."
	@mkdir -p addons etc postgresql
	@chmod -R 777 addons etc postgresql 2>/dev/null || sudo chmod -R 777 addons etc postgresql

scaffold:
	@echo "Scaffolding module $(MODULE) in addons/..."
	$(COMPOSE) exec odoo20 odoo scaffold $(MODULE) /mnt/extra-addons

upgrade:
	docker exec $(CONTAINER) odoo --db_host=$(DB_HOST) -d $(DB_NAME) -r $(DB_USER) -w $(DB_PASSWORD) -u $(MODULE) --stop-after-init

upgrade-all:
	docker exec $(CONTAINER) odoo --db_host=$(DB_HOST) -d $(DB_NAME) -r $(DB_USER) -w $(DB_PASSWORD) -u all --stop-after-init

upgrade-all-debug:
	docker exec $(CONTAINER) odoo --db_host=$(DB_HOST) -d $(DB_NAME) -r $(DB_USER) -w $(DB_PASSWORD) -u all --stop-after-init --log-level=debug --logfile=/dev/stdout

wait-db:
	@docker exec $(DB_CONTAINER) sh -c 'until pg_isready -U $(DB_USER) -h 127.0.0.1; do echo "Waiting for PostgreSQL..."; sleep 2; done'

wait-odoo:
	@echo "Waiting for Odoo registry to load (HTTP)..."
	@until docker exec $(CONTAINER) python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8069/web/login', timeout=5)" >/dev/null 2>&1; do echo "Loading registry..."; sleep 2; done
	@echo "Odoo registry loaded."

ensure-up:
	$(COMPOSE) up -d odoo20

restart-upgrade: wait-db ensure-up wait-odoo upgrade
	$(COMPOSE) restart odoo20

restart-upgrade-all: wait-db ensure-up wait-odoo upgrade-all
	$(COMPOSE) restart odoo20
