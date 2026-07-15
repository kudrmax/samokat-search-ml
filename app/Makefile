VENV := /Users/maxos/PythonProjects/LSH/.venv
PYTHON := $(VENV)/bin/python
HOST := 127.0.0.1
PORT := 8000
PIDFILE := .uvicorn.pid
LOGFILE := .uvicorn.log

.PHONY: up down restart logs status

up:
	@if [ -f $(PIDFILE) ] && kill -0 `cat $(PIDFILE)` 2>/dev/null; then \
		echo "Уже запущено (pid `cat $(PIDFILE)`) на http://$(HOST):$(PORT)"; \
	else \
		$(PYTHON) -m uvicorn backend.main:app --host $(HOST) --port $(PORT) > $(LOGFILE) 2>&1 & \
		echo $$! > $(PIDFILE); \
		echo "Запущено на http://$(HOST):$(PORT) (pid `cat $(PIDFILE)`), логи: $(LOGFILE)"; \
	fi

down:
	@if [ -f $(PIDFILE) ] && kill -0 `cat $(PIDFILE)` 2>/dev/null; then \
		kill `cat $(PIDFILE)` && echo "Остановлено (pid `cat $(PIDFILE)`)"; \
	else \
		echo "Не запущено — нечего останавливать"; \
	fi

restart: down up

status:
	@if [ -f $(PIDFILE) ] && kill -0 `cat $(PIDFILE)` 2>/dev/null; then \
		echo "Работает (pid `cat $(PIDFILE)`) на http://$(HOST):$(PORT)"; \
	else \
		echo "Остановлено"; \
	fi

logs:
	@tail -f $(LOGFILE)
