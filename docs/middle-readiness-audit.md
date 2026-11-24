# Middle-readiness audit — Data Analyst Portfolio

**Проверено:** 24 November 2026  
**Репозиторий:** https://github.com/blvxx/analyst-portfolio  
**Целевая роль:** Data Analyst / Marketing Analyst  
**Оценка относится к доказательствам в GitHub-портфолио, а не к общему уровню профессионального опыта кандидата.**

## Итог

**Текущий уровень портфолио: Stage 3 — Pre-middle, близко к Stage 4.**

Три проекта используют реальные открытые источники, все три полных ETL были выполнены в Docker Compose, данные проверены, SQL/DuckDB-агрегаты сверены с Python там, где это реализовано, тесты и CI проходят.

Главный оставшийся критерий, который не позволяет честно поставить Stage 4 по исходному чек-листу: **публичный URL интерактивных дашбордов ещё не включён**. GitHub Actions уже собрал статический сайт и Pages artifact; для публикации владелец репозитория должен один раз выбрать GitHub Actions в Settings → Pages и запустить workflow вручную.

Эта оценка намеренно строже, чем «в репозитории есть три ноутбука»: она учитывает реальные запуски, источники, очистку, ограничения и проверяемые артефакты.

## 1. Доказательства по проектам

### 01. Marketing Analytics

**Источник:** UCI Online Shoppers Purchasing Intention, CC BY 4.0, DOI 10.24432/C5F88Q.  
**Покрытие:** 12,330 исследовательских сессий, 1,908 сессий с покупкой.

Результат полного запуска 24.11.2026:

- Сессии: 12,330.
- Покупки: 1,908.
- Наблюдаемая конверсия: 15.47%.
- SQL/DuckDB и pandas сверили число сессий, покупки и агрегаты по типу посетителя.
- Тест связи VisitorType × Revenue: χ² p-value = 4.27e-30; Cramér's V = 0.1047; минимальная ожидаемая частота = 13.15.
- 125 точных повторяющихся строк отмечены, но не удалены автоматически; 124 сессии отмечены в верхнем 1% распределения суммарной длительности. Пропусков в исходном наборе не найдено.

**Методы:** conversion rate, сегментация по VisitorType / TrafficType / Month, Wilson 95% confidence intervals, χ², Cramér's V, DuckDB SQL.

**Ограничения:** TrafficType — кодированная категория без названия рекламной платформы. Нет рекламных расходов, атрибуции, прибыли и суммы заказа; CAC, ROAS, ROI и причинный эффект маркетинга не рассчитываются. Статистическая значимость при большом объёме наблюдений не означает сильный эффект: Cramér's V здесь 0.1047.

**Файлы:** pipeline.py, run.py, sql/queries.sql, tests/test_pipeline.py, findings.md и dashboard.html создаются при запуске.

### 02. E-commerce Analytics

**Источник:** UCI Online Retail II, CC BY 4.0, DOI 10.24432/C5CG6D.  
**Покрытие:** 1,067,371 исходная строка транзакций (2009–2011).

Результат полного запуска 24.11.2026:

- Исходные строки: 1,067,371.
- Строки продаж после документированных правил: 1,044,415.
- Уникальные счета: 41,938.
- Идентифицированные клиенты: 5,881.
- Повторные клиенты: 4,255 (72.35% от клиентов с Customer ID).
- Валовая сумма положительных строк продаж: £20,972,594.57.
- Доля строк продаж без Customer ID: 22.86%.
- Взвешенное month-1 cohort retention: 23.13%.
- SQL/DuckDB и pandas сверили месячную выручку и число счетов, а также количество клиентов по RFM-сегментам.

**Методы:** очистка транзакций, обработка отмен/возвратов, monthly sales, AOV, RFM scoring и именованные сегменты, cohort retention, оконные функции SQL, агрегаты DuckDB.

**Правила качества:** префикс C в InvoiceNo и отрицательные Quantity исключаются из gross sales; нулевая цена сохраняется для бесплатных позиций/образцов; отрицательные цены исключаются. Отсутствующий Customer ID не удаляет строку из продаж, но исключает её из RFM и когорт. 12,133 точных дубликата подсчитаны и отмечены, а не удалены без бизнес-основания. Когортные месяцы без повторной покупки явно представлены нулевой активностью.

**Ограничения:** один исторический британский retailer, данные 2009–2011, заметная доля строк без Customer ID, нет себестоимости, маржи, рекламных расходов или источников привлечения. Gross sales не matched/refund-adjusted net revenue; возвраты анализируются отдельно, а не связываются с каждой исходной продажей.

**Файлы:** pipeline.py, run.py, sql/queries.sql, tests/test_pipeline.py, findings.md, summary.json, quality_report.json, sql_reconciliation.json и dashboard.html.

### 03. CIS Macro Analytics

**Источник:** World Bank Indicators API v2, World Development Indicators, source ID 2.  
**Покрытие:** 6 стран × 25 лет (2000–2024), 4 индикатора.

Результат полного запуска 24.11.2026:

- API observations: 600.
- Полная панель country-year: 150 строк.
- Дубликатов ключа country-year-indicator: 0.
- Пропуски оставлены без импутации: GDP per capita — 0; internet users — 3; inflation — 11; unemployment — 0.
- SQL/DuckDB сверил количество строк long-form и полной панели с DataFrame; уникальность ключа country-year проверяется отдельно.

**Индикаторы:** GDP per capita (current US$), internet users (% population), CPI inflation (%), unemployment (ILO modeled estimate, %).

**Методы:** API ingestion с пагинацией и retry/backoff, нормализация ISO-2/ISO-3 country codes, long-to-wide panel, first/last observation trend, pairwise Pearson correlations и pair counts, полнота данных, DuckDB SQL.

**Ограничения:** текущие USD не отражают реальный экономический рост; показатели публикуются с разным лагом; unemployment — модельная оценка ILO; корреляция на агрегатах стран не доказывает причинность. Относительное процентное изменение не выводится для нулевой/отрицательной базы.

**Файлы:** pipeline.py, run.py, sql/queries.sql, tests/test_pipeline.py, findings.md, quality_report.json, sql_reconciliation.json и dashboard.html.

## 2. Инженерная проверка

| Требование | Результат | Доказательство |
|---|---|---|
| 2–3 проекта на реальных данных | Выполнено | UCI sessions, UCI transactions, World Bank API |
| Источник и лицензия | Выполнено | README каждого проекта |
| Получение данных из источника | Выполнено | UCI ZIP/XLSX download, World Bank API pagination |
| Работа с пропусками/дубликатами/выбросами | Выполнено | quality_report.json каждого проекта, явные правила |
| SQL на реальном объёме | Выполнено | DuckDB и 1,067,371 исходных строк в E-commerce |
| SQL/Python reconciliation | Выполнено | sql_reconciliation.json; для macro сравниваются row counts и ключи |
| Автоматизированные тесты | Выполнено | 14 unit-тестов |
| Docker / Docker Compose | Выполнено | Все три ETL запущены в контейнерах; тесты повторно прошли в контейнере |
| CI | Выполнено | GitHub Actions: tests + compile + Docker tests |
| Воспроизводимость | Выполнено | requirements.txt, Dockerfile, docker-compose.yml, Makefile и команды запуска |
| Git-история | Выполнено | Последовательные коммиты кода, тестов, документации и workflow |
| Публичные интерактивные дашборды | Не завершено | Статический сайт собран как GitHub Actions artifact, но Pages ещё не включён |
| Реальный внешний пользователь / коммерческое использование | Не заявляется | Проекты — независимая практика на открытых данных |

## 3. Результаты CI и полных запусков

- [Real Data Pipelines and Dashboards — полный Docker ETL и сборка сайта](https://github.com/blvxx/analyst-portfolio/actions/runs/45392112722)
- [Artifact: analyst-dashboards-site](https://github.com/blvxx/analyst-portfolio/actions/runs/45392112722/artifacts/14919741852)
- [CI: tests, compileall и Docker Compose tests](https://github.com/blvxx/analyst-portfolio/actions/runs/45392554572)

В публичный artifact входят только агрегаты, отчёты, CSV для визуализаций и HTML-дашборды. Построчные session data и транзакции с идентификаторами клиентов в site artifact не включаются.

## 4. Что осталось до Stage 4

1. В GitHub открыть Settings → Pages и выбрать **Source: GitHub Actions**.
2. Открыть Actions → **Real Data Pipelines and Dashboards** → Run workflow.
3. Убедиться, что шаг **Deploy GitHub Pages (manual runs only)** завершился успешно и появился публичный URL.
4. Добавить этот URL в GitHub profile README и резюме Data Analyst.

До появления публичного dashboard URL текущую оценку следует сохранять как **Stage 3 — Pre-middle**. После публикации всех трёх дашбордов и повторной проверки доступности портфолио можно повторно оценивать по Stage 4. Для Stage 5 понадобится уже не только портфолио, но и доказательство использования реальным пользователем, OSS-вклада или production-практики.

## 5. Честные границы

Это портфолио демонстрирует аналитику на открытых данных, data quality, SQL, Python, воспроизводимость и визуализацию. Оно не доказывает коммерческую работу аналитиком, владение внутренними данными компании, влияние на реальные продажи или production ownership. В резюме эти проекты следует обозначать как independent/open-data analytics projects.
