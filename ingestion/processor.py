"""
ingestion/processor.py  —  raw databook Excel -> processed CSV (one per sheet).

Returns a ProcessResult instead of printing. Warnings (unmapped sheet names,
per-file failures) used to go to stdout, where nobody reading Telegram ever saw
them; now they travel back with the result and the caller decides how to show
them. Unmapped sheets in particular are silent data loss, so they must surface.

Output location comes from config.paths.PROCESSED_DIR — the same object
storage/loader.py reads from, so the write path and the read path cannot drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from config.paths import PROCESSED_DIR
from config.sheet_keys import key_for_sheet

EXCEL_SUFFIXES = (".xlsx", ".xlsm", ".xls")
DATE_HEADER = "일자"


@dataclass
class ProcessResult:
    """What one processing pass produced, plus everything worth telling the user."""

    files: list[str] = field(default_factory=list)      # "key.csv (원본: book.xlsm)"
    warnings: list[str] = field(default_factory=list)   # recoverable: unmapped sheet
    errors: list[str] = field(default_factory=list)     # a whole file failed

    def __len__(self) -> int:
        return len(self.files)

    def __bool__(self) -> bool:
        return bool(self.files)

    def telegram_lines(self) -> list[str]:
        """Report body: what was written, then what went wrong."""
        lines = [f"- {f}" for f in self.files]
        lines += [f"!! {w}" for w in self.warnings]
        lines += [f"!! {e}" for e in self.errors]
        return lines


def excel_files(source_dir: Path) -> list[Path]:
    """Real workbooks in a folder: no Excel lock files (~$...)."""
    if not source_dir.exists():
        return []
    return [
        f for f in source_dir.iterdir()
        if f.is_file() and f.suffix.lower() in EXCEL_SUFFIXES
        and not f.name.startswith("~$")
    ]


def _split_indicator_blocks(raw_df: pd.DataFrame) -> list[pd.DataFrame]:
    """One databook sheet holds several indicators side by side, each starting at
    a '일자' column. Cut the sheet at those columns and tidy each block."""
    date_indices = [i for i, col in enumerate(raw_df.columns) if DATE_HEADER in str(col)]
    if not date_indices:
        return []

    blocks = []
    for idx, start_col in enumerate(date_indices):
        end_col = date_indices[idx + 1] if idx + 1 < len(date_indices) else raw_df.shape[1]
        subset = raw_df.iloc[:, start_col:end_col].copy()
        if subset.shape[1] < 2:
            continue

        indicator_name = raw_df.columns[start_col][0]
        if pd.isna(indicator_name) or str(indicator_name).startswith("Unnamed"):
            indicator_name = f"지표_{start_col}"

        subset.columns = [DATE_HEADER] + [
            f"{indicator_name}_val_{j}" for j in range(1, subset.shape[1])
        ]
        subset = subset.dropna(subset=[DATE_HEADER])
        subset[DATE_HEADER] = subset[DATE_HEADER].astype(str).str.strip()
        subset = subset.drop_duplicates(subset=[DATE_HEADER]).set_index(DATE_HEADER)
        blocks.append(subset)
    return blocks


def process_excel_data(base_dir: str | Path | None = None) -> ProcessResult:
    """Rebuild every processed CSV from the raw Excel books in base_dir.

    base_dir defaults to RAW_DIR. One bad workbook never stops the others: its
    failure is recorded in result.errors and the pass continues.
    """
    source_dir = Path(base_dir) if base_dir else None
    if source_dir is None:
        from config.paths import RAW_DIR
        source_dir = RAW_DIR

    result = ProcessResult()
    target_dir = PROCESSED_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    files = excel_files(source_dir)
    if not files:
        result.warnings.append(f"처리할 Excel 파일 없음: {source_dir}")
        return result

    for file_path in files:
        try:
            all_sheets = pd.read_excel(file_path, sheet_name=None, header=[0, 1])
        except Exception as e:  # noqa: BLE001
            result.errors.append(f"{file_path.name} 읽기 실패: {e}")
            continue

        for sheet_name, raw_df in all_sheets.items():
            try:
                raw_df = raw_df.dropna(how="all")
                if raw_df.empty:
                    continue
                blocks = _split_indicator_blocks(raw_df)
                if not blocks:
                    continue

                sheet_df = (
                    pd.concat(blocks, axis=1)
                    .reset_index()
                    .sort_values(DATE_HEADER, ascending=False)
                )

                canonical_key, matched = key_for_sheet(sheet_name)
                if not matched:
                    result.warnings.append(
                        f"미매핑 시트 '{sheet_name}' -> '{canonical_key}.csv' "
                        f"(config/sheet_keys.py 에 추가하세요)"
                    )

                out_name = f"{canonical_key}.csv"
                sheet_df.to_csv(target_dir / out_name, index=False, encoding="utf-8-sig")
                result.files.append(f"{out_name} (원본: {file_path.name})")
            except Exception as e:  # noqa: BLE001
                result.errors.append(f"{file_path.name}/{sheet_name} 처리 실패: {e}")

    return result
