@echo off
rem 项目启动参数。以后优先修改本文件，不要直接改启动/关闭脚本。

set "SERVER_NAME=127.0.0.1"
set "SERVER_PORT=7860"
set "GRADIO_EXTRA_ARGS="

rem Python 运行方式。PYTHON_EXE 留空时，默认使用 mamba run -n %MAMBA_ENV% python。
set "MAMBA_EXE=mamba"
set "MAMBA_ENV=yolo"
if not defined PYTHON_EXE set "PYTHON_EXE="

rem 运行时目录。该目录已被 Git 忽略，不会提交到仓库。
set "YOLO_CONFIG_DIR=%PROJECT_ROOT%outputs\ultralytics-config"
