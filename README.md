# Data Analytics — Project Evidence

> **Portfolio navigation:** the employer-facing overview is the [single career portfolio](https://blvxx.github.io/portfolio/). This repository contains reproducible analytics projects, data pipelines, SQL/Python analysis and dashboard evidence.


**Target roles:** Data Analyst · Marketing Analyst · BI / Reporting Analyst  
**Stack:** Python · SQL · pandas · DuckDB · Plotly

[Открыть опубликованные интерактивные дашборды](https://blvxx.github.io/analyst-portfolio/) · [Посмотреть исходный код и ETL](https://github.com/blvxx/analyst-portfolio)

Портфолио из трёх воспроизводимых аналитических проектов на открытых реальных данных. Проекты показывают полный аналитический цикл: получение данных, очистку и проверку качества, SQL/Python-анализ, формирование бизнес-метрик, интерпретацию ограничений и публикацию дашбордов.

## Что можно проверить за несколько минут

- **Marketing Analytics:** 12 330 исследовательских сессий, 1 908 покупок, конверсия 15,47%; сегментация и статистическая проверка различий.
- **E-commerce Analytics:** 1 067 371 исходная строка транзакций; очистка, возвраты, RFM и когортный анализ.
- **CIS Macro Analytics:** 6 стран × 25 лет; загрузка через World Bank API, обработка пропусков и сравнение временных рядов.

> Это самостоятельные кейсы на открытых данных, а не коммерческие проекты. Исторические и методологические ограничения приведены ниже; выводы не подменяют измерение реального эффекта для бизнеса.

> Все выводы должны быть заново рассчитаны из исходных данных при запуске. Числа в примерах не подменяют фактические результаты. Датасеты не хранятся в Git: загрузка выполняется из первоисточников.

## Проекты

| Проект | Бизнес-вопрос | Данные | Основные методы |
|---|---|---|---|
| [01. Marketing Analytics](./projects/01_marketing_analytics/) | Какие характеристики сессии связаны с покупкой и где отличаются конверсии? | UCI Online Shoppers Purchasing Intention, 12 330 реальных сессий | очистка, conversion rate, сегментация, χ², Cramér's V, SQL |
| [02. E-commerce Analytics](./projects/02_ecommerce_analytics/) | Как меняются продажи, клиентская база, повторные покупки и когорты? | UCI Online Retail II, 1 067 371 строк транзакций | ETL, data quality, RFM, когортный анализ, SQL/DuckDB |
| [03. CIS Macro Analytics](./projects/03_cis_macro_analytics/) | Как менялись цифровое развитие и экономические показатели стран СНГ? | World Bank Indicators API, временные ряды по странам и годам | API ingestion, обработка пропусков, сравнение трендов, корреляции |

## Быстрый старт

Требуется Python 3.11+.

1. Создать виртуальное окружение и установить зависимости:

    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

   На Windows PowerShell: .venv\Scripts\Activate.ps1

2. Запустить интересующий проект:

    python projects/01_marketing_analytics/run.py
    python projects/02_ecommerce_analytics/run.py
    python projects/03_cis_macro_analytics/run.py

3. Запустить проверки:

    pytest -q

Каждый pipeline загружает источник, сохраняет неизменённую копию в локальном каталоге data/raw, формирует очищенные таблицы, CSV-отчёты, DuckDB-файл, отчёт с выводами и интерактивный HTML-дашборд в каталоге outputs соответствующего проекта. Каталоги data и outputs не коммитятся. Для больших запусков и повторяемой среды используется Docker Compose.

## Запуск через Docker Compose

Требуется Docker Desktop / Docker Engine с Docker Compose v2.

    docker compose run --build --rm tests
    docker compose run --build --rm marketing
    docker compose run --build --rm ecommerce
    docker compose run --build --rm macro

Или через Makefile:

    make docker-test
    make docker-marketing
    make docker-ecommerce
    make docker-macro

Исходные данные и результаты сохраняются в каталогах каждого проекта, чтобы их можно было повторно использовать и изучать вне контейнера. Локальные данные лежат под игнорируемыми Git-путями и не отправляются в репозиторий.

## Структура

    projects/
      01_marketing_analytics/
        pipeline.py
        run.py
        sql/queries.sql
        tests/test_pipeline.py
      02_ecommerce_analytics/
        pipeline.py
        run.py
        sql/queries.sql
        tests/test_pipeline.py
      03_cis_macro_analytics/
        pipeline.py
        run.py
        sql/queries.sql
        tests/test_pipeline.py

## Источники и лицензии

- UCI Online Shoppers Purchasing Intention: https://archive.ics.uci.edu/dataset/468/online+shoppers+purchasing+intention+dataset — CC BY 4.0. Citation: Sakar & Kastro (2018), DOI 10.24432/C5F88Q.
- UCI Online Retail II: https://archive.ics.uci.edu/dataset/502/online+retail+ii — CC BY 4.0. Citation: Chen (2012), DOI 10.24432/C5CG6D.
- World Bank Indicators API: https://datahelpdesk.worldbank.org/knowledgebase/articles/889392 — для собственных наборов данных Всемирного банка обычно применяется CC BY 4.0; отдельные источники могут иметь другие условия. Проверяйте метаданные конкретного набора. Общие условия: https://datacatalog.worldbank.org/public-licenses.

## Методологические принципы

- Сохранять исходные данные отдельно и не перезаписывать их очищенной версией.
- Не удалять выбросы автоматически: сначала измерить, описать и объяснить решение.
- Не заполнять пропуски без методологического основания. В макроданных пропуски сохраняются и показываются в отчёте.
- Разделять наблюдаемую ассоциацию и причинно-следственную связь.
- Для транзакций отдельно учитывать отмены и возвраты; не считать их обычными продажами.
- Для когорт использовать уникальных клиентов и явно определённую дату первой покупки.
- Не публиковать персональные данные. В этих проектах используются обезличенные исследовательские данные и агрегированные публичные показатели.

## Ограничения портфолио

Это самостоятельные аналитические кейсы на открытых данных, а не коммерческие проекты и не результаты для реальных заказчиков. Датасет онлайн-магазина исторический (2009–2011), поэтому он подходит для демонстрации методов, но не для выводов о современном e-commerce. Данные о веб-сессиях опубликованы в исследовательских целях и не содержат рекламных расходов, поэтому ROAS, CAC и инкрементальный эффект каналов рассчитать нельзя. World Bank API обновляется и может пересматривать исторические значения; время выгрузки фиксируется в metadata.

## Middle-readiness audit

[Открыть подробный аудит готовности портфолио](./docs/middle-readiness-audit.md) — источники и лицензии, результаты полных запусков, data quality, SQL/Python reconciliation, Docker/CI, публичные дашборды и ограничения. Оценка отражает полноту технического портфолио, а не подтверждает коммерческий стаж Middle-аналитика.

## Проверенный запуск на реальных данных

**Последний подтверждённый полный запуск: 24 ноября 2026 года.** Все три pipeline были выполнены на первоисточниках в GitHub Actions; проверки объёма данных, качества и SQL/Python-сверки прошли.

| Проект | Фактический результат |
|---|---|
| Marketing Analytics | 12 330 сессий, 1 908 покупок, конверсия 15,47%; SQL/DuckDB и pandas сверены |
| E-commerce Analytics | 1 067 371 исходная строка, 1 044 415 строк продаж, 41 938 счетов, 5 881 идентифицированный клиент; валовая выручка £20 972 594,57; повторные клиенты 72,35%; SQL/Python сверка прошла |
| CIS Macro Analytics | 600 записей API, 150 строк полной панели (6 стран × 25 лет), 14 пропусков, 0 дубликатов ключей; SQL/Python сверка прошла |

**Важные оговорки:** маркетинговая конверсия относится к исследовательским сессиям и не является ROAS/ROI. E-commerce набор исторический (2009–2011), валовая выручка исключает отмены и отрицательные количества, а клиентская аналитика использует только строки с Customer ID. Макроданные — агрегаты World Bank; ВВП на душу населения в текущих USD не является реальным экономическим ростом, а корреляции не доказывают причинность.

- [Последний полный Docker-запуск, сборка и публикация GitHub Pages — 24.11.2026](https://github.com/blvxx/analyst-portfolio/actions/runs/45394565431)
- [CI: unit-тесты и компиляция](https://github.com/blvxx/analyst-portfolio/actions/runs/45392554572)

CI проверяет тесты, синтаксис Python и повторно выполняет 14 unit-тестов внутри Docker Compose; отдельный workflow запускает все три ETL внутри Docker, загружает полные исходники, проверяет ожидаемый объём и SQL/Python reconciliation, собирает интерактивные HTML-дашборды. В публичный артефакт входят только агрегированные результаты и визуализации, не построчные сессии и не клиентские ID.

## Лицензия

Код репозитория распространяется по MIT License. Лицензии исходных наборов данных отличаются и указаны выше; лицензия кода не заменяет лицензию данных.


## Опубликованные интерактивные дашборды

Статический сайт с агрегированными результатами опубликован через GitHub Pages. В нём доступны три интерактивных дашборда, аналитические выводы и ссылки на исходный код.

- [Главная страница аналитического портфолио](https://blvxx.github.io/analyst-portfolio/)
- [01. Marketing Analytics — конверсия и поведение посетителей](https://blvxx.github.io/analyst-portfolio/01_marketing_analytics/dashboard.html)
- [02. E-commerce Analytics — продажи, RFM и когорты](https://blvxx.github.io/analyst-portfolio/02_ecommerce_analytics/dashboard.html)
- [03. CIS Macro Analytics — макроэкономические показатели стран СНГ](https://blvxx.github.io/analyst-portfolio/03_cis_macro_analytics/dashboard.html)
- [GitHub Pages deployment — успешный запуск 24.11.2026](https://github.com/blvxx/analyst-portfolio/actions/runs/45394565431)

Публикуются только агрегированные отчёты и визуализации. Построчные пользовательские сессии и транзакции с клиентскими идентификаторами в Pages artifact не включаются. Повторный запуск workflow пересобирает данные и обновляет опубликованные дашборды.

## Дополнительный опубликованный retail-кейс

В более раннем инженерном архиве уже есть отдельная работа на реальных данных UCI Online Retail — 541 909 строк транзакций, воспроизводимая очистка, возвраты, RFM, когорты, SQL-сверка и опубликованные агрегированные результаты. Это смежный исторический кейс, а не один из трёх новых проектов в этом репозитории:

- [Опубликованная страница Customer Retention & Sales Analytics](https://blvxx.github.io/portfolio/customer-retention-analytics/)
- [README и методология исходного проекта](https://github.com/blvxx/portfolio/tree/main/customer-retention-analytics)

В отчёте исходного проекта зафиксированы результаты, рассчитанные из UCI workbook, а не синтетические значения. Датасет также исторический (2010–2011), и все ограничения описаны в самом кейсе.

## Смежный инженерный кейс: Data Quality и ETL QA

Дополняющий проект по тестированию слоёв хранилища PostgreSQL, оркестрации Airflow, сверке source-to-target, повторным запускам и DQ-проверкам: [DWH Data Quality & ETL Testing Platform](https://github.com/blvxx/qa-engineering-portfolio/tree/main/dwh-data-quality-testing). Это отдельная инженерная лаборатория на синтетических данных, а не один из трёх аналитических проектов на открытых данных выше.
