@echo off
chcp 65001 > nul
echo =========================================
echo   正在更新/安装打包依赖 (PyInstaller & Rich)
echo =========================================
:: 建议同时更新 rich 确保版本一致
pip install --upgrade pyinstaller rich

echo.
echo =========================================
echo   开始打包 Plaso-DL (修复 Rich 依赖)
echo =========================================

:: 核心修改点：添加了 --hidden-import 强制包含 Unicode 数据
:: 如果您的报错版本号不同，请将 17-0-0 改为报错中显示的数字
pyinstaller --noconfirm --clean --onefile ^
 --name "Plaso-DL-App" ^
 --hidden-import="rich._unicode_data.unicode17-0-0" ^
 --add-data "src/plaso_dl/static;plaso_dl/static" ^
 plaso_dl_app.py

echo.
echo =========================================
echo   打包完成！
echo   如果仍报错，请确认报错中的 unicode 版本号
echo =========================================
pause