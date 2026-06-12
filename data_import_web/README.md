# 数据导入系统部署文档

## 系统要求

- Python 3.7+
- Oracle Client (Instant Client)
- 操作系统: Windows/Linux

## 安装步骤

### 1. 安装Oracle Instant Client

**Windows:**
```bash
# 下载Oracle Instant Client
# https://www.oracle.com/database/technologies/instant-client/downloads.html
# 解压到 C:\oracle\instantclient_19_x
# 添加到系统PATH环境变量
```

**Linux:**
```bash
# 下载并解压
wget https://download.oracle.com/otn_software/linux/instantclient/instantclient-basic-linux.x64-19.x.zip
unzip instantclient-basic-linux.x64-19.x.zip -d /opt/oracle
echo /opt/oracle/instantclient_19_x > /etc/ld.so.conf.d/oracle-instantclient.conf
ldconfig
```

### 2. 安装Python依赖

```bash
cd data_import_web
pip install -r requirements.txt
```

### 3. 配置数据库连接

设置环境变量（可选，默认值已配置）：

```bash
# Windows
set DB_USER=datagrid
set DB_PASSWORD=datagrid
set DB_HOST=192.168.84.39
set DB_PORT=1521
set DB_SERVICE=NINVOICE

# Linux
export DB_USER=datagrid
export DB_PASSWORD=datagrid
export DB_HOST=192.168.84.39
export DB_PORT=1521
export DB_SERVICE=NINVOICE
```

### 4. 启动应用

```bash
python app.py
```

应用将在 http://localhost:5000 启动

## 使用说明

1. 打开浏览器访问 http://localhost:5000
2. 选择要导入的SQL文件
3. 点击"上传并导入"按钮
4. 等待处理完成，查看结果

## API接口

### 发票数据导入
```
POST /api/import/invoice
Content-Type: multipart/form-data
参数: file (SQL文件)
```

### 税务数据导入
```
POST /api/import/tax
Content-Type: multipart/form-data
参数: file (SQL文件)
```

## 生产环境部署

### 使用Gunicorn (Linux)

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### 使用Nginx反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 使用systemd服务 (Linux)

创建 `/etc/systemd/system/data-import.service`:

```ini
[Unit]
Description=Data Import Web Service
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/data_import_web
Environment="DB_USER=datagrid"
Environment="DB_PASSWORD=datagrid"
Environment="DB_HOST=192.168.84.39"
ExecStart=/usr/bin/gunicorn -w 4 -b 127.0.0.1:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
systemctl daemon-reload
systemctl start data-import
systemctl enable data-import
```

## 故障排查

### Oracle连接失败
- 检查Oracle Client是否正确安装
- 检查环境变量配置
- 验证数据库连接信息

### 文件上传失败
- 检查uploads目录权限
- 确认文件大小不超过100MB

### 导入数据错误
- 检查SQL文件格式
- 查看错误日志
- 验证数据库表结构

## 项目结构

```
data_import_web/
├── app.py              # Flask主应用
├── import_invoice.py   # 发票导入模块
├── import_tax.py       # 税务导入模块
├── requirements.txt    # Python依赖
├── templates/          # HTML模板
│   └── index.html
└── uploads/            # 临时上传目录
```
