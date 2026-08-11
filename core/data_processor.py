import os
import pandas as pd
from pathlib import Path


def process_excel_data(base_dir: str):
    source_dir = Path(base_dir)
    target_dir = Path(r"C:\Users\User\databook_processed")
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
            # 1. 파일 안의 모든 시트 읽기
            all_sheets = pd.read_excel(file_path, sheet_name=None, header=[0, 1])

            print(f"\n[디버그 파일명]: {file_path.name}")
            print(f"[디버그 감지된 시트 목록]: {list(all_sheets.keys())}")

            for sheet_name, raw_df in all_sheets.items():
                print(f" -> 처리 중인 시트 이름: '{sheet_name}' (행/열 크기: {raw_df.shape})")

                raw_df = raw_df.dropna(how='all')
                if raw_df.empty:
                    print(f"    [스킵] '{sheet_name}' 시트가 비어있음")
                    continue

                date_indices = [i for i, col in enumerate(raw_df.columns) if '일자' in str(col)]
                if not date_indices:
                    print(f"    [스킵] '{sheet_name}' 시트에서 '일자' 컬럼을 못 찾음")
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
                    subset = subset.drop_duplicates(subset=['일자'])
                    subset = subset.set_index('일자')

                    sheet_dfs.append(subset)

                if not sheet_dfs:
                    print(f"    [스킵] '{sheet_name}' 시트에서 유효한 데이터 블록을 못 건짐")
                    continue

                sheet_df = pd.concat(sheet_dfs, axis=1)
                sheet_df = sheet_df.reset_index()
                sheet_df = sheet_df.sort_values('일자', ascending=False)

                safe_sheet_name = str(sheet_name).strip().replace(" ", "_")

                # 이름은 시트 이름으로 고정!
                new_file_name = f"{safe_sheet_name}.csv"

                sheet_df.to_csv(target_dir / new_file_name, index=False, encoding="utf-8-sig")

                # 텔레그램에서 참고할 수 있도록 원본 파일명과 시트(저장파일명)를 함께 기록
                info_str = f"{new_file_name} (원본: {file_path.name})"
                processed_files.append(info_str)

                print(f"    [저장 완료] {new_file_name}")

        except Exception as e:
            print(f"[에러] {file_path.name} 처리 실패: {e}")

    print(f"[디버그 최종 반환 목록]: {processed_files}")
    return processed_files