from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from task_automation_studio.core.models import RecordInput, RecordResult


class ExcelConnector:
    REQUIRED_COLUMNS = ("first_name", "last_name", "email")

    def read_records(self, file_path: str | Path, sheet_name: str | int = 0) -> list[RecordInput]:
        df = pd.read_excel(file_path, sheet_name=sheet_name, dtype=str).fillna("")
        missing_columns = [col for col in self.REQUIRED_COLUMNS if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns in Excel file: {', '.join(missing_columns)}")

        records: list[RecordInput] = []
        for row in df[list(self.REQUIRED_COLUMNS)].to_dict(orient="records"):
            records.append(
                RecordInput(
                    first_name=row["first_name"].strip(),
                    last_name=row["last_name"].strip(),
                    email=row["email"].strip(),
                )
            )
        return records

    def write_results(
        self,
        file_path: str | Path,
        results: list[RecordResult],
        output_sheet_name: str = "automation_results",
    ) -> None:
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        rows: list[dict[str, Any]] = []
        for result in results:
            rows.append(
                {
                    "first_name": result.record.first_name,
                    "last_name": result.record.last_name,
                    "email": result.record.email,
                    "status": result.status.value,
                    "error_code": result.error_code or "",
                    "error_message": result.error_message or "",
                }
            )

        output_df = pd.DataFrame(rows)
        if not file_path.exists():
            with pd.ExcelWriter(file_path, mode="w", engine="openpyxl") as writer:
                output_df.to_excel(writer, sheet_name=output_sheet_name, index=False)
            return

        with pd.ExcelWriter(file_path, mode="a", if_sheet_exists="replace", engine="openpyxl") as writer:
            output_df.to_excel(writer, sheet_name=output_sheet_name, index=False)
