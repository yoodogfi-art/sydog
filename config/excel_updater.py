import os
import subprocess
import time
import win32com.client
from external_uploader.telegram_uploader import send_telegram_message


def run_excel_updaters(base_dir):
  file_dict = {
      "KOFR_bonds": r"korea_kofr_databook.xlsm",
      "KOFR_strat": r"Z:/자산운용/301. 펀드운용업무/전략운용본부/FX 관리/data/KR__KOFR_DATABOOK.xlsm"
  }

  print("엑셀 데이터북 자동 갱신 프로세스 시작...\n")

  for df_name, rel_path in file_dict.items():
    file_path = os.path.abspath(os.path.join(base_dir, rel_path))
    print(f"[{df_name}] 파일 실행 중: {file_path}")

    if not os.path.exists(file_path):
      print(f"  └ [오류] 파일을 찾을 수 없습니다\n")
      send_telegram_message(
          f"*[Databook Error]*\n- 대상: `{df_name}`\n- 에러: 파일 없음"
      )
      continue

    try:
      # 1. 서브프로세스로 몰래 실행 (API 안 뜯김)
      subprocess.Popen(["start", "", file_path], shell=True)
      print(
          f"  └ [대기 중] API 로딩 및 데이터 갱신을 위해 30초간 대기 중..."
      )

      # 2. 파이썬이 밖에서 30초 동안 얌전히 대기 (API가 데이터를 빨아들이는 시간)
      time.sleep(30)

      # 3. 30초가 지난 후, 이미 켜져 있는 엑셀에 접근해서 저장 및 닫기 수행
      print(f"  └ [저장 중] A3 검증 및 저장/종료 처리 중...")

      excel_app = win32com.client.GetActiveObject("Excel.Application")
      target_filename = os.path.basename(file_path)

      target_wb = None
      for wb in excel_app.Workbooks:
        if wb.Name.lower() == target_filename.lower():
          target_wb = wb
          break

      status_msg = "불일치"
      today_str = time.strftime("%Y-%m-%d")

      if target_wb:
        # A3 셀 확인
        a3_val = str(target_wb.Sheets(1).Range("A3").Value)

        if today_str in a3_val:
          status_msg = f"일치 (A3: {a3_val})"
        else:
          status_msg = f"불일치 (A3: {a3_val})"

        # 저장 후 닫기
        target_wb.Save()
        target_wb.Close(SaveChanges=True)
      else:
        # 혹시 창을 못 찾았을 경우의 예외 처리
        print(f"  └ [경고] 열려있는 워크북 목록에서 파일을 찾지 못함")

      print(f"  └ [완료] 결과: {status_msg}\n")

      # 4. 텔레그램 전송
      msg = (
          f"*[Databook Update Result]*\n- 대상: `{df_name}`\n- 상태:"
          f" `{status_msg}`"
      )
      send_telegram_message(msg)

    except Exception as e:
      print(f"  └ [에러 발생]: {e}\n")
      send_telegram_message(
          f"*[Databook Update Error]*\n- 대상: `{df_name}`\n- 에러: `{e}`"
      )

  print("tasks done successfully!")