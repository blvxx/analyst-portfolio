from pathlib import Path

from pipeline import load_workbook, download_source, prepare_sales, build_outputs

if __name__ == "__main__":
    project_dir = Path(__file__).resolve().parent
    workbook = download_source(project_dir / "data" / "raw")
    raw = load_workbook(workbook)
    sales, quality = prepare_sales(raw)
    build_outputs(sales, quality, project_dir / "outputs")
    print(f"E-commerce analytics complete: {len(sales):,} sale lines")
    print(f"Dashboard: {project_dir / 'outputs' / 'dashboard.html'}")
