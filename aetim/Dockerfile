# -----------------------------------------------------------------
# AETIM 系統 Docker 映像檔
# -----------------------------------------------------------------

# 1. 基底映像檔：使用一個穩定、輕量的 Python 3.10 版本
FROM python:3.10-slim-bullseye

# 2. 設定工作目錄
WORKDIR /app

# 3. 安裝系統依賴 (有些 Python 套件需要編譯)
RUN apt-get update && apt-get install -y \
    build-essential \
    sqlite3 \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 3.1. 設定時區為 Asia/Taipei (UTC+8)
ENV TZ=Asia/Taipei
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 4. 複製依賴清單
# (我們先複製這個檔案，以便 Docker 善用快取)
COPY requirements.txt .

# 5. 安裝 Python 依賴
RUN pip install --no-cache-dir -r requirements.txt

# 6. 複製所有專案檔案到工作目錄
COPY . .

# 7. (*** 變更 ***)
# 預設指令改為啟動我們的主排程器 (階段二)
# 這個腳本將被設計為常駐執行
CMD ["python", "scheduler.py"]

# 7. 預設指令 (當容器啟動時，自動執行資料庫初始化)
# CMD ["python", "setup_database.py"]

# 8. 暴露應用程式埠口 (如果有需要)
# EXPOSE 8000