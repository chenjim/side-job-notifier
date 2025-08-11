# 使用官方 Playwright Python 镜像（包含 Chromium 和所有依赖）
FROM mcr.microsoft.com/playwright/python:v1.55.0-jammy

# 设置时区为亚洲/上海（中国标准时间）
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 设置环境变量以禁用 Python 输出缓冲
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8

# Playwright 环境变量
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

COPY requirements.txt .

# 安装 Python 依赖（Playwright 已经预装在镜像中）
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

COPY . .

CMD ["python", "-u", "main.py"]