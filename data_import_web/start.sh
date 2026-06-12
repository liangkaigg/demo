#!/bin/bash

# 后台启动Flask应用
nohup python3 app.py > app.log 2>&1 &
echo "应用已在后台启动，日志输出到 app.log"
