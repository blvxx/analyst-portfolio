from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
PROJECTS = [
    ("01_marketing_analytics", "Marketing Analytics", "Конверсия сессий и поведение онлайн-покупателей"),
    ("02_ecommerce_analytics", "E-commerce Analytics", "Продажи, RFM и когортное удержание"),
    ("03_cis_macro_analytics", "CIS Macro Analytics", "Показатели цифрового развития и макроэкономики"),
]


def main() -> None:
    SITE.mkdir(parents=True, exist_ok=True)
    links = []
    for slug, title, description in PROJECTS:
        source = ROOT / "projects" / slug / "outputs" / "dashboard.html"
        if not source.exists():
            raise FileNotFoundError(
                f"Dashboard is missing: {source}. Run the corresponding project pipeline first."
            )
        destination_dir = SITE / slug
        destination_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination_dir / "dashboard.html")
        links.append(
            "<li><a href='" + slug + "/dashboard.html'>" + title + "</a>"
            "<p>" + description + "</p></li>"
        )

    page = "\n".join([
        "<!doctype html>",
        '<html lang="ru"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Analyst Portfolio — Dashboards</title>",
        "<style>",
        "body{font:16px/1.6 system-ui,sans-serif;max-width:900px;margin:48px auto;padding:0 20px;color:#172033;background:#f7f8fb}",
        "h1{font-size:2rem}li{margin:22px 0;padding:20px;background:white;border:1px solid #e4e8ef;border-radius:14px}",
        "a{color:#2457c5;font-weight:700}p{margin:6px 0;color:#5c6678}",
        "</style></head><body>",
        "<h1>Analyst Portfolio — интерактивные дашборды</h1>",
        "<p>Три аналитических кейса на открытых реальных данных. Источники, методология и ограничения описаны в GitHub-репозитории.</p>",
        "<ul>",
        *links,
        "</ul>",
        '<p><a href="https://github.com/blvxx/analyst-portfolio">Исходный код и инструкции на GitHub</a></p>',
        "</body></html>",
    ])
    (SITE / "index.html").write_text(page, encoding="utf-8")
    print(f"Static dashboard site created at {SITE}")


if __name__ == "__main__":
    main()
