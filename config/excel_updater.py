import os
import time


def run_excel_updaters(base_dir):
    # 파일 위치 딕셔너리
    file_dict = {
        "asia_northeast_govt_bonds": "asia_northeast_govt_databook.xlsm",
        "KODR": "korea_kofr_databook.xlsm",
        "test": "krate.xlsm"
    }

    print("엑셀 데이터북 자동 갱신 프로세스 시작...\n")

    for df_name, rel_path in file_dict.items():
        file_path = os.path.join(base_dir, rel_path)
        print(f"[{df_name}] 파일 실행 중: {file_path}")

        if not os.path.exists(file_path):
            print(f"  └ [오류] 파일을 찾을 수 없습니다: {file_path}\n")
            continue

        try:
            os.startfile(file_path)
            print(f"  └ [실행 완료] VBA가 자동으로 갱신 및 날짜 확인을 수행합니다.\n")
            time.sleep(5)

        except Exception as e:
            print(f"  └ [에러 발생]: {e}\n")

    print("tasks done successfully!")