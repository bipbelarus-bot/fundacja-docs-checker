from __future__ import annotations

from pathlib import Path
import pandas as pd


def write_reports(rows: list[dict], output_path: str | Path) -> tuple[Path, Path]:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.suffix.lower() == ".csv":
        csv_path = output_path
        xlsx_path = output_path.with_suffix(".xlsx")
    else:
        csv_path = output_path.with_suffix(".csv")
        xlsx_path = output_path.with_suffix(".xlsx")

    df = pd.DataFrame(rows, columns=["file", "check", "status", "message"])
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="findings")
        if not df.empty:
            summary = (
                df.groupby(["status", "check"], dropna=False)
                .size()
                .reset_index(name="count")
                .sort_values(["status", "check"])
            )
            summary.to_excel(writer, index=False, sheet_name="summary")
    return csv_path, xlsx_path
