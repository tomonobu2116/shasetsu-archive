@echo off
rem ============================================================
rem  社説アーカイブ更新 ランチャー（ダブルクリック用）
rem  同じフォルダにある update_shasetsu.ps1 を実行します。
rem  タスクスケジューラからは、このbatを指定すればOKです。
rem ============================================================

rem このbatが置かれているフォルダへ移動
cd /d "%~dp0"

rem PowerShellスクリプトを実行
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0update_shasetsu.ps1"

rem 結果を確認できるよう10秒だけ表示して自動で閉じる
rem （pause だとタスクスケジューラの無人実行で止まるため timeout を使用）
echo.
echo ----------------------------------------
echo 処理が終了しました。10秒後に自動で閉じます。
echo すぐ閉じる場合は何かキーを押してください。
echo ----------------------------------------
timeout /t 10