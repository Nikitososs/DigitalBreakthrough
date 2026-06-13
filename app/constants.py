"""Единые константы домена ZeroProblems.

Без зависимостей от других модулей app/* — можно импортировать откуда угодно
без риска циклических импортов.
"""

# ID служебной задачи единого live-потока обращений граждан (Postgres).
# Зашит синхронно в backend и frontend/src/constants.js — менять только вместе.
LIVE_STREAM_TASK_ID = "live0000"

# Префикс row_id обращений граждан (live). Excel-строки имеют числовые row_id
# и не удаляются через live API.
CITIZEN_ROW_PREFIX = "citizen-"
