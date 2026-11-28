from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"

PROJECTS = [
    {
        "slug": "01_marketing_analytics",
        "title": "Marketing Analytics",
        "description": "Конверсия, типы посетителей, трафик и статистическая неопределённость",
        "safe_outputs": [
            "findings.md", "overall_metrics.json", "quality_report.json",
            "statistical_tests.json", "sql_reconciliation.json",
            "conversion_by_visitor.csv", "conversion_by_traffic.csv",
            "conversion_by_month.csv",
        ],
    },
    {
        "slug": "02_ecommerce_analytics",
        "title": "E-commerce Analytics",
        "description": "Исторические продажи, возвраты, RFM и когортное удержание",
        "safe_outputs": [
            "findings.md", "summary.json", "quality_report.json", "sql_reconciliation.json",
            "monthly_sales.csv", "country_sales.csv", "cohort_retention.csv",
            "rfm_segment_summary.csv",
        ],
    },
    {
        "slug": "03_cis_macro_analytics",
        "title": "CIS Macro Analytics",
        "description": "Макроэкономические индикаторы и цифровое развитие стран СНГ",
        "safe_outputs": [
            "findings.md", "quality_report.json", "sql_reconciliation.json",
            "macro_panel.csv", "indicator_trends.csv", "latest_snapshot.csv",
            "indicator_correlations.csv", "correlation_pair_counts.csv",
        ],
    },
]


STATIC_CASES = [
    {
        "slug": "customer-retention-analytics",
        "title": "Customer Retention & Sales Analytics",
        "description": "UCI Online Retail: очистка транзакций, возвраты, RFM, повторные покупки и когортное удержание",
        "copy_generated": True,
    },
    {
        "slug": "subscription-revenue-analytics",
        "title": "Subscription Revenue & Retention Analytics",
        "description": "PostgreSQL BI: MRR / ARR, revenue bridge, churn, expansion, cohorts и quality checks на синтетической модели подписок",
        "copy_generated": False,
    },
]


def copy_required(source_dir: Path, destination_dir: Path, filenames: list[str]) -> None:
    destination_dir.mkdir(parents=True, exist_ok=True)
    for filename in filenames:
        source = source_dir / filename
        if not source.exists():
            raise FileNotFoundError(f"Expected generated output is missing: {source}")
        shutil.copy2(source, destination_dir / filename)


def render_project_card(project: dict[str, object]) -> str:
    slug = str(project["slug"])
    title = str(project["title"])
    description = str(project["description"])
    return (
        "<article><h2>" + title + "</h2><p>" + description + "</p>"
        '<p><a href="' + slug + '/dashboard.html">Открыть интерактивный дашборд</a> '
        '| <a href="https://github.com/blvxx/Data-Analytics-Projects-Dashboards/tree/main/projects/'
        + slug + '">Исходный код и методология</a> '
        '| <a href="' + slug + '/data/findings.md">Аналитические выводы</a></p>'
        "</article>"
    )


def main() -> None:
    SITE.mkdir(parents=True, exist_ok=True)
    cards: list[str] = []
    for project in PROJECTS:
        slug = str(project["slug"])
        source_dir = ROOT / "projects" / slug / "outputs"
        destination_dir = SITE / slug
        dashboard = source_dir / "dashboard.html"
        if not dashboard.exists():
            raise FileNotFoundError(
                f"Dashboard is missing: {dashboard}. Run the corresponding pipeline first."
            )
        destination_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dashboard, destination_dir / "dashboard.html")
        copy_required(source_dir, destination_dir / "data", list(project["safe_outputs"]))
        cards.append(render_project_card(project))

    for case in STATIC_CASES:
        slug = str(case["slug"])
        source_dir = ROOT / "projects" / slug
        destination_dir = SITE / slug
        source_page = source_dir / "index.html"
        if not source_page.exists():
            raise FileNotFoundError(f"Static case page is missing: {source_page}")
        destination_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_page, destination_dir / "index.html")
        if bool(case["copy_generated"]):
            generated = source_dir / "docs" / "generated"
            if not generated.exists():
                raise FileNotFoundError(f"Generated public report is missing: {generated}")
            shutil.copytree(generated, destination_dir / "docs" / "generated", dirs_exist_ok=True)
        cards.append(
            "<article><h2>" + str(case["title"]) + "</h2><p>" + str(case["description"]) + "</p>"
            '<p><a href="' + slug + '/">Открыть кейс</a> '
            '| <a href="https://github.com/blvxx/Data-Analytics-Projects-Dashboards/tree/main/projects/'
            + slug + '">Исходный код и методология</a></p></article>'
        )

    page = "\n".join([
        "<!doctype html>",
        '<html lang="ru"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Data Analytics — Projects & Dashboards</title>",
        "<style>",
        "body{font:16px/1.65 system-ui,sans-serif;max-width:1040px;margin:48px auto;padding:0 22px;color:#182235;background:#f5f7fb}",
        "header{margin-bottom:34px}h1{font-size:2.2rem;line-height:1.2}header p{color:#5b6678}",
        "article{margin:18px 0;padding:24px;background:#fff;border:1px solid #e3e8f1;border-radius:16px;box-shadow:0 8px 26px rgba(25,40,70,.04)}",
        "a{color:#2359c4;font-weight:650;text-decoration:none}a:hover{text-decoration:underline}",
        "footer{margin-top:38px;color:#667085;font-size:.92rem}",
        "</style></head><body>",
        "<header><h1>Data Analytics Projects & Dashboards</h1>",
        "<p>Пять аналитических кейсов: три воспроизводимых pipeline на открытых данных и два отдельных направления Customer Retention и Subscription Revenue. Для каждого доступны методология, ограничения и исходные материалы.</p>",
        "<p>Проекты — независимые аналитические работы на публичных данных, не коммерческие клиентские кейсы.</p></header>",
        *cards,
        '<footer><a href="https://github.com/blvxx/Data-Analytics-Projects-Dashboards">Исходный код на GitHub</a> · '
        '<a href="https://github.com/blvxx">Профиль GitHub</a></footer>',
        "</body></html>",
    ])
    (SITE / "index.html").write_text(page, encoding="utf-8")
    print(f"Static dashboard site created at {SITE}")


if __name__ == "__main__":
    main()
