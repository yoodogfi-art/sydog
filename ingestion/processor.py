import os
import pandas as pd
from pathlib import Path

from config.sheet_keys import key_for_sheet


def process_excel_data(base_dir: str):
    source_dir = Path(base_dir)
    target_dir = Path(os.getenv("PROCESSED_DIR", r"C:\Users\User\databook_processed"))
    target_dir.mkdir(parents=True, exist_ok=True)

    excel_extensions = (".xlsx", ".xlsm", ".xls")
    files = [
        f for f in source_dir.iterdir()
        if f.is_file() and f.suffix.lower() in excel_extensions and not f.name.startswith("~$")
    ]
    if not files:
        print("[알림] 처리할 파일이 없습니다.")
        return []

    processed_files = []
    for file_path in files:
        try:
            all_sheets = pd.read_excel(file_path, sheet_name=None, header=[0, 1])
            for sheet_name, raw_df in all_sheets.items():
                raw_df = raw_df.dropna(how='all')
                if raw_df.empty:
                    continue
                date_indices = [i for i, col in enumerate(raw_df.columns) if '일자' in str(col)]
                if not date_indices:
                    continue
                sheet_dfs = []
                for idx, start_col in enumerate(date_indices):
                    end_col = date_indices[idx + 1] if idx + 1 < len(date_indices) else raw_df.shape[1]
                    subset = raw_df.iloc[:, start_col:end_col].copy()
                    if subset.shape[1] < 2:
                        continue
                    indicator_name = raw_df.columns[start_col][0]
                    if pd.isna(indicator_name) or str(indicator_name).startswith("Unnamed"):
                        indicator_name = f"지표_{start_col}"
                    subset.columns = ['일자'] + [f"{indicator_name}_val_{j}" for j in range(1, subset.shape[1])]
                    subset = subset.dropna(subset=['일자'])
                    subset['일자'] = subset['일자'].astype(str).str.strip()
                    subset = subset.drop_duplicates(subset=['일자']).set_index('일자')
                    sheet_dfs.append(subset)
                if not sheet_dfs:
                    continue
                sheet_df = pd.concat(sheet_dfs, axis=1).reset_index().sort_values('일자', ascending=False)

                canonical_key, matched = key_for_sheet(sheet_name)
                if not matched:
                    print(f"    [경고] 미매핑 시트 '{sheet_name}' -> '{canonical_key}.csv'. sheet_keys.py에 추가하세요.")
                new_file_name = f"{canonical_key}.csv"

                sheet_df.to_csv(target_dir / new_file_name, index=False, encoding="utf-8-sig")
                processed_files.append(f"{new_file_name} (원본: {file_path.name})")
        except Exception as e:
            print(f"[에러] {file_path.name} 처리 실패: {e}")
    return processed_files