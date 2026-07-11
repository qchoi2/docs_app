@echo off
REM 계약서 검색 웹앱 실행 런처.
REM 어느 폴더에서 실행해도 이 배치 파일이 있는 프로젝트 폴더로 이동한 뒤
REM 프로젝트에 포함된 로컬 색인(cs_index)을 대상으로 웹 API를 띄운다.
REM 다른 색인을 쓰려면:  run_webapp.bat C:\my_index
cd /d "%~dp0"

set "INDEX=%~1"
if "%INDEX%"=="" set "INDEX=cs_index"

if not exist "%INDEX%\catalog.sqlite" (
  echo [오류] "%INDEX%\catalog.sqlite" 을 찾을 수 없습니다.
  echo        먼저 색인을 만들었는지, 색인 경로가 맞는지 확인하세요.
  echo        예: run_webapp.bat C:\cs_index
  pause
  exit /b 1
)

echo 웹앱 실행 중... 브라우저에서 http://127.0.0.1:8765 을 여세요. (종료: Ctrl+C)
python webapp.py --out "%INDEX%"
pause
