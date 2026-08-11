import os
import subprocess
import time
import win32com.client
import pythoncom
from pathlib import Path
from external_uploader.telegram_uploader import send_telegram_message


def run_excel_updaters(base_dir):
    try:
        pythoncom.CoInitialize()
    except Exception:
        pass

    source_dir = Path(base_dir)

    # 1. base_dir 안의 모든 엑셀 파일 자동 검색 (.xlsx, .xlsm, .xls)
    excel_extensions = (".xlsx", ".xlsm", ".xls")
    files = [f for f in source_dir.iterdir() if f.is_file() and f.suffix.lower() in excel_extensions]

    # Z 드라이브 등 외부 경로에 있는 필수 파일 추가
    external_files = [
        Path(r"Z:/자산운용/301. 펀드운용업무/전략운용본부/FX 관리/data/KR__KOFR_DATABOOK.xlsm"),
        Path(r"Z:/자산운용/404. 채권팀회의자료/데일리파일/미국장/미국장_0.2.2/global_dailyreport_databook.xlsm")
    ]

    # 로컬 base_dir 파일들과 외부 필수 파일들을 하나로 합치기 (중복 제거)
    all_files = list(set(files + [f for f in external_files if f.exists()]))

    if not all_files:
        print("[알림] 업데이트할 엑셀 파일이 없습니다.")
        return []

    print(f"엑셀 데이터북 자동 갱신 프로세스 시작... (총 {len(all_files)}개 파일)\n")
    results = []

    for file_path in all_files:
        # 확장자를 떼고 파일명을 이름으로 사용
        df_name = file_path.stem
        print(f"[{df_name}] 파일 실행 중: {file_path}")

        try:
            # 1. 서브프로세스로 엑셀 창 실행 (API 차단 우회)
            subprocess.Popen(["start", "", str(file_path)], shell=True)
            print(f"  └ [대기 중] API 로딩 및 데이터 갱신을 위해 30초간 대기 중...")

            # 2. 30초 대기
            time.sleep(30)

            # 3. 켜져 있는 엑셀 객체 가져와서 A3 검증 및 저장
            print(f"  └ [저장 중] A3 검증 및 저장/종료 처리 중...")
            excel_app = win32com.client.GetActiveObject("Excel.Application")
            target_filename = file_path.name

            target_wb = None
            for wb in excel_app.Workbooks:
                if wb.Name.lower() == target_filename.lower():
                    target_wb = wb
                    break

            status_msg = "불일치"
            today_str = time.strftime("%Y-%m-%d")

            if target_wb:
                # 첫 번째 시트의 A3 셀 확인
                a3_val = str(target_wb.Sheets(1).Range("A3").Value)
                if today_str in a3_val:
                    status_msg = f"일치 (A3: {a3_val})"
                else:
                    status_msg = f"불일치 (A3: {a3_val})"

                target_wb.Save()
                target_wb.Close(SaveChanges=True)
            else:
                print(f"  └ [경고] 열려있는 워크북 목록에서 파일을 찾지 못함")

            print(f"  └ [완료] 결과: {status_msg}\n")
            results.append((df_name, status_msg))

            # 4. 텔레그램 전송
            msg = f"*[Databook Update Result]*\n- 대상: `{df_name}`\n- 상태: `{status_msg}`"
            send_telegram_message(msg)

        except Exception as e:
            print(f"  └ [에러 발생]: {e}\n")
            err_msg = f"*[Databook Update Error]*\n- 대상: `{df_name}`\n- 에러: `{e}`"
            send_telegram_message(err_msg)
            results.append((df_name, f"에러: {e}"))

    print("tasks done successfully!")
    return results