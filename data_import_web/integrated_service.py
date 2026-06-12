# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from functools import wraps
import logging
from logging.handlers import RotatingFileHandler
import os
from flask_cors import CORS

from db_service import (
    get_invoice_db_connection,
    get_tax_db_connection,
    detect_encoding,
    read_csv,
    delete_invoice_data,
    make_invoice_data,
    delete_tax_data,
    make_tax_data,
    delete_export_tax_data,
    make_export_tax_data,
    delete_income_tax_data,
    make_income_tax_data
)

# 初始化Flask应用
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24).hex())
CORS(app, supports_credentials=True)

# ==================== 管理员配置 ====================
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')


def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            is_api = request.path.startswith('/api/')
            if is_api:
                return jsonify({'error': '未登录，请先登录'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/login', methods=['GET', 'POST'])
def login():
    """管理员登录页面"""
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['logged_in'] = True
            session['username'] = username
            app.logger.info(f'Admin login successful: {username}')
            return redirect(url_for('index'))
        app.logger.warning(f'Admin login failed: {username}')
        return render_template('login.html', error='用户名或密码错误')
    return render_template('login.html')


@app.route('/logout')
def logout():
    """管理员登出"""
    session.clear()
    return redirect(url_for('login'))

# 配置日志
if not os.path.exists('logs'):
    os.makedirs('logs')
    
file_handler = RotatingFileHandler('invoice_service.log',backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Invoice and Tax service startup')

# 配置根日志，使db_service的日志也能被捕获
root_logger = logging.getLogger()
root_logger.addHandler(file_handler)
root_logger.setLevel(logging.INFO)

# ==================== API路由 ====================
@app.route('/api/invoice/process', methods=['POST'])
@login_required
def process_invoice_data():
    """
    处理发票数据的API接口
    接收JSON格式数据: {"nsrsbh": "纳税人识别号", "company": "企业名称"}
    """
    try:
        # 获取请求数据
        data = request.get_json()
        
        if not data:
            app.logger.warning('No JSON data received')
            return jsonify({'error': 'No JSON data received'}), 400
        
        nsrsbh = data.get('nsrsbh')
        company = data.get('company')
        
        if not nsrsbh or not company:
            app.logger.warning('Missing nsrsbh or company in request')
            return jsonify({'error': 'Missing nsrsbh or company'}), 400
        
        app.logger.info(f'Processing invoice data: nsrsbh={nsrsbh}, company={company}')
        
        # 获取数据库连接
        conn = get_invoice_db_connection()
        cursor = conn.cursor()
        
        try:
            # 执行删除操作
            if not delete_invoice_data(nsrsbh, cursor):
                return jsonify({'error': 'Failed to delete existing invoice data'}), 500
            
            # 执行插入和更新操作
            if not make_invoice_data(company, nsrsbh, cursor):
                return jsonify({'error': 'Failed to insert/update invoice data'}), 500
            
            # 提交事务
            conn.commit()
            app.logger.info('Invoice database transaction committed successfully')
            
            return jsonify({
                'success': True,
                'message': f'Invoice data processed successfully for nsrsbh: {nsrsbh}, company: {company}'
            }), 200
            
        except Exception as e:
            conn.rollback()
            app.logger.error(f'Invoice database operation failed: {e}')
            return jsonify({'error': f'Invoice database operation failed: {str(e)}'}), 500
            
        finally:
            cursor.close()
            conn.close()
            app.logger.info('Invoice database connection closed')
            
    except Exception as e:
        app.logger.error(f'Unexpected error in invoice processing: {e}')
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/api/invoice/process/csv', methods=['POST'])
@login_required
def process_invoice_csv():
    """
    处理CSV文件的API接口 - 发票数据
    接收包含CSV文件的请求
    """
    try:
        # 检查是否有文件上传
        if 'file' not in request.files:
            app.logger.warning('No file uploaded')
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            app.logger.warning('No file selected')
            return jsonify({'error': 'No file selected'}), 400
        
        # 保存上传的文件
        csv_path = os.path.join('uploads', file.filename)
        if not os.path.exists('uploads'):
            os.makedirs('uploads')
        file.save(csv_path)
        app.logger.info(f'File saved: {csv_path}')
        
        # 读取CSV数据
        datas = read_csv(csv_path)
        
        if not datas:
            return jsonify({'error': 'No valid data found in CSV'}), 400
        
        app.logger.info(f'Processing {len(datas)} rows from CSV for invoice data')
        
        # 获取数据库连接
        conn = get_invoice_db_connection()
        cursor = conn.cursor()
        
        results = []
        
        try:
            for data in datas:
                if len(data) < 2:
                    continue
                    
                nsrsbh = data[0]
                company = data[1]
                
                app.logger.info(f'Processing invoice data: nsrsbh={nsrsbh}, company={company}')
                
                # 执行删除操作
                if not delete_invoice_data(nsrsbh, cursor):
                    results.append({
                        'nsrsbh': nsrsbh,
                        'company': company,
                        'status': 'error',
                        'message': 'Failed to delete existing invoice data'
                    })
                    continue
                
                # 执行插入和更新操作
                if not make_invoice_data(company, nsrsbh, cursor):
                    results.append({
                        'nsrsbh': nsrsbh,
                        'company': company,
                        'status': 'error',
                        'message': 'Failed to insert/update invoice data'
                    })
                    continue
                
                results.append({
                    'nsrsbh': nsrsbh,
                    'company': company,
                    'status': 'success',
                    'message': 'Invoice data processed successfully'
                })
            
            # 提交事务
            conn.commit()
            app.logger.info('Invoice database transaction committed successfully')
            
            # 删除上传的文件
            #os.remove(csv_path)
            
            return jsonify({
                'success': True,
                'processed': len(results),
                'results': results
            }), 200
            
        except Exception as e:
            conn.rollback()
            app.logger.error(f'Invoice database operation failed: {e}')
            return jsonify({'error': f'Invoice database operation failed: {str(e)}'}), 500
            
        finally:
            cursor.close()
            conn.close()
            app.logger.info('Invoice database connection closed')
            
    except Exception as e:
        app.logger.error(f'Unexpected error in invoice CSV processing: {e}')
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/api/tax/process', methods=['POST'])
@login_required
def process_tax_data():
    """
    处理税收数据的API接口
    接收JSON格式数据: {"nsrsbh": "纳税人识别号", "company": "企业名称", "name": "联系人姓名(可选)", "zjhm": "证件号码(可选)", "num": "数据条数(可选，默认10000)"}
    """
    try:
        # 获取请求数据
        data = request.get_json()
        
        if not data:
            app.logger.warning('No JSON data received')
            return jsonify({'error': 'No JSON data received'}), 400
        
        nsrsbh = data.get('nsrsbh')
        company = data.get('company')
        name = data.get('name')
        zjhm = data.get('zjhm')
        num = data.get('num', 10000)
        
        if not nsrsbh or not company:
            app.logger.warning('Missing nsrsbh or company in request')
            return jsonify({'error': 'Missing nsrsbh or company'}), 400
        
        app.logger.info(f'Processing tax data: nsrsbh={nsrsbh}, company={company}, name={name}, zjhm={zjhm}, num={num}')
        
        # 获取数据库连接
        conn = get_tax_db_connection()
        cursor = conn.cursor()
        
        try:
            # 执行删除操作
            if not delete_tax_data(nsrsbh, cursor):
                return jsonify({'error': 'Failed to delete existing tax data'}), 500
            
            # 执行插入操作
            if not make_tax_data(nsrsbh, company, name, zjhm, num, cursor):
                return jsonify({'error': 'Failed to insert tax data'}), 500
            
            # 提交事务
            conn.commit()
            app.logger.info('Tax database transaction committed successfully')
            
            return jsonify({
                'success': True,
                'message': f'Tax data processed successfully for nsrsbh: {nsrsbh}, company: {company}'
            }), 200
            
        except Exception as e:
            conn.rollback()
            app.logger.error(f'Tax database operation failed: {e}')
            return jsonify({'error': f'Tax database operation failed: {str(e)}'}), 500
            
        finally:
            cursor.close()
            conn.close()
            app.logger.info('Tax database connection closed')
            
    except Exception as e:
        app.logger.error(f'Unexpected error in tax processing: {e}')
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/api/tax/process/csv', methods=['POST'])
@login_required
def process_tax_csv():
    """
    处理CSV文件的API接口 - 税收数据
    接收包含CSV文件的请求
    """
    try:
        # 检查是否有文件上传
        if 'file' not in request.files:
            app.logger.warning('No file uploaded')
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            app.logger.warning('No file selected')
            return jsonify({'error': 'No file selected'}), 400
        
        # 保存上传的文件
        csv_path = os.path.join('uploads', file.filename)
        if not os.path.exists('uploads'):
            os.makedirs('uploads')
        file.save(csv_path)
        app.logger.info(f'File saved: {csv_path}')
        
        # 读取CSV数据
        datas = read_csv(csv_path)
        
        if not datas:
            return jsonify({'error': 'No valid data found in CSV'}), 400
        
        app.logger.info(f'Processing {len(datas)} rows from CSV for tax data')
        
        # 获取数据库连接
        conn = get_tax_db_connection()
        cursor = conn.cursor()
        
        results = []
        
        try:
            for data in datas:
                if len(data) < 2:
                    continue
                    
                nsrsbh = data[0]
                company = data[1]
                
                app.logger.info(f'Processing tax data: nsrsbh={nsrsbh}, company={company}')
                
                # 执行删除操作
                if not delete_tax_data(nsrsbh, cursor):
                    results.append({
                        'nsrsbh': nsrsbh,
                        'company': company,
                        'status': 'error',
                        'message': 'Failed to delete existing tax data'
                    })
                    continue
                
                # 执行插入操作
                if not make_tax_data(nsrsbh, company, None, None, 10000, cursor):
                    results.append({
                        'nsrsbh': nsrsbh,
                        'company': company,
                        'status': 'error',
                        'message': 'Failed to insert tax data'
                    })
                    continue
                
                results.append({
                    'nsrsbh': nsrsbh,
                    'company': company,
                    'status': 'success',
                    'message': 'Tax data processed successfully'
                })
            
            # 提交事务
            conn.commit()
            app.logger.info('Tax database transaction committed successfully')
            
            # 删除上传的文件
            #os.remove(csv_path)
            
            return jsonify({
                'success': True,
                'processed': len(results),
                'results': results
            }), 200
            
        except Exception as e:
            conn.rollback()
            app.logger.error(f'Tax database operation failed: {e}')
            return jsonify({'error': f'Tax database operation failed: {str(e)}'}), 500
            
        finally:
            cursor.close()
            conn.close()
            app.logger.info('Tax database connection closed')
            
    except Exception as e:
        app.logger.error(f'Unexpected error in tax CSV processing: {e}')
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

# ==================== 出口退税API路由 ====================
@app.route('/api/export/process', methods=['POST'])
@login_required
def process_export_tax_data():
    """
    处理出口退税数据的API接口
    接收JSON格式数据: {"nsrsbh": "纳税人识别号"}
    """
    try:
        # 获取请求数据
        data = request.get_json()
        
        if not data:
            app.logger.warning('No JSON data received')
            return jsonify({'error': 'No JSON data received'}), 400
        
        nsrsbh = data.get('nsrsbh')
        
        if not nsrsbh:
            app.logger.warning('Missing nsrsbh in request')
            return jsonify({'error': 'Missing nsrsbh'}), 400
        
        app.logger.info(f'Processing export tax data: nsrsbh={nsrsbh}')
        
        # 获取数据库连接
        conn = get_tax_db_connection()
        cursor = conn.cursor()
        
        try:
            # 执行删除操作
            if not delete_export_tax_data(nsrsbh, cursor):
                return jsonify({'error': 'Failed to delete existing export tax data'}), 500
            
            # 执行插入操作
            if not make_export_tax_data(nsrsbh, cursor):
                return jsonify({'error': 'Failed to insert export tax data'}), 500
            
            # 提交事务
            conn.commit()
            app.logger.info('Export tax database transaction committed successfully')
            
            return jsonify({
                'success': True,
                'message': f'Export tax data processed successfully for nsrsbh: {nsrsbh}'
            }), 200
            
        except Exception as e:
            conn.rollback()
            app.logger.error(f'Export tax database operation failed: {e}')
            return jsonify({'error': f'Export tax database operation failed: {str(e)}'}), 500
            
        finally:
            cursor.close()
            conn.close()
            app.logger.info('Export tax database connection closed')
            
    except Exception as e:
        app.logger.error(f'Unexpected error in export tax processing: {e}')
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/api/export/process/csv', methods=['POST'])
@login_required
def process_export_tax_csv():
    """
    处理CSV文件的API接口 - 出口退税数据
    接收包含CSV文件的请求
    """
    try:
        # 检查是否有文件上传
        if 'file' not in request.files:
            app.logger.warning('No file uploaded')
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            app.logger.warning('No file selected')
            return jsonify({'error': 'No file selected'}), 400
        
        # 保存上传的文件
        csv_path = os.path.join('uploads', file.filename)
        if not os.path.exists('uploads'):
            os.makedirs('uploads')
        file.save(csv_path)
        app.logger.info(f'File saved: {csv_path}')
        
        # 读取CSV数据
        datas = read_csv(csv_path)
        
        if not datas:
            return jsonify({'error': 'No valid data found in CSV'}), 400
        
        app.logger.info(f'Processing {len(datas)} rows from CSV for export tax data')
        
        # 获取数据库连接
        conn = get_tax_db_connection()
        cursor = conn.cursor()
        
        results = []
        
        try:
            for data in datas:
                if len(data) < 1:
                    continue
                    
                nsrsbh = data[0]
                
                app.logger.info(f'Processing export tax data: nsrsbh={nsrsbh}')
                
                # 执行删除操作
                if not delete_export_tax_data(nsrsbh, cursor):
                    results.append({
                        'nsrsbh': nsrsbh,
                        'status': 'error',
                        'message': 'Failed to delete existing export tax data'
                    })
                    continue
                
                # 执行插入操作
                if not make_export_tax_data(nsrsbh, cursor):
                    results.append({
                        'nsrsbh': nsrsbh,
                        'status': 'error',
                        'message': 'Failed to insert export tax data'
                    })
                    continue
                
                results.append({
                    'nsrsbh': nsrsbh,
                    'status': 'success',
                    'message': 'Export tax data processed successfully'
                })
            
            # 提交事务
            conn.commit()
            app.logger.info('Export tax database transaction committed successfully')
            
            # 删除上传的文件
            #os.remove(csv_path)
            
            return jsonify({
                'success': True,
                'processed': len(results),
                'results': results
            }), 200
            
        except Exception as e:
            conn.rollback()
            app.logger.error(f'Export tax database operation failed: {e}')
            return jsonify({'error': f'Export tax database operation failed: {str(e)}'}), 500
            
        finally:
            cursor.close()
            conn.close()
            app.logger.info('Export tax database connection closed')
            
    except Exception as e:
        app.logger.error(f'Unexpected error in export tax CSV processing: {e}')
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


@app.route('/api/incometax/process', methods=['POST'])
@login_required
def process_income_tax_data():
    """
    处理所得税数据的API接口
    接收JSON格式数据: {"nsrsbh": "纳税人识别号"}
    """
    try:
        # 获取请求数据
        data = request.get_json()
        
        if not data:
            app.logger.warning('No JSON data received')
            return jsonify({'error': 'No JSON data received'}), 400
        
        nsrsbh = data.get('nsrsbh')
        
        if not nsrsbh:
            app.logger.warning('Missing nsrsbh in request')
            return jsonify({'error': 'Missing nsrsbh'}), 400
        
        app.logger.info(f'Processing income tax data: nsrsbh={nsrsbh}')
        
        # 获取数据库连接
        conn = get_tax_db_connection()
        cursor = conn.cursor()
        
        try:
            # 执行删除操作
            if not delete_income_tax_data(nsrsbh, cursor):
                return jsonify({'error': 'Failed to delete existing income tax data'}), 500
            
            # 执行插入操作
            if not make_income_tax_data(nsrsbh, cursor):
                return jsonify({'error': 'Failed to insert income tax data'}), 500
            
            # 提交事务
            conn.commit()
            app.logger.info('Income tax database transaction committed successfully')
            
            return jsonify({
                'success': True,
                'message': f'Income tax data processed successfully for nsrsbh: {nsrsbh}'
            }), 200
            
        except Exception as e:
            conn.rollback()
            app.logger.error(f'Income tax database operation failed: {e}')
            return jsonify({'error': f'Income tax database operation failed: {str(e)}'}), 500
            
        finally:
            cursor.close()
            conn.close()
            app.logger.info('Income tax database connection closed')
            
    except Exception as e:
        app.logger.error(f'Unexpected error in income tax processing: {e}')
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/api/incometax/process/csv', methods=['POST'])
@login_required
def process_income_tax_csv():
    """
    处理CSV文件的API接口 - 所得税数据
    接收包含CSV文件的请求
    """
    try:
        # 检查是否有文件上传
        if 'file' not in request.files:
            app.logger.warning('No file uploaded')
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['file']

        if file.filename == '':
            app.logger.warning('No file selected')
            return jsonify({'error': 'No file selected'}), 400

        # 保存上传的文件
        csv_path = os.path.join('uploads', file.filename)
        if not os.path.exists('uploads'):
            os.makedirs('uploads')
        file.save(csv_path)
        app.logger.info(f'File saved: {csv_path}')

        # 读取CSV数据
        datas = read_csv(csv_path)

        if not datas:
            return jsonify({'error': 'No valid data found in CSV'}), 400

        app.logger.info(f'Processing {len(datas)} rows from CSV for income tax data')

        # 获取数据库连接
        conn = get_tax_db_connection()
        cursor = conn.cursor()

        results = []

        try:
            for data in datas:
                if len(data) < 1:
                    continue

                nsrsbh = data[0]

                app.logger.info(f'Processing income tax data: nsrsbh={nsrsbh}')

                # 执行删除操作
                if not delete_income_tax_data(nsrsbh, cursor):
                    results.append({
                        'nsrsbh': nsrsbh,
                        'status': 'error',
                        'message': 'Failed to delete existing income tax data'
                    })
                    continue

                # 执行插入操作
                if not make_income_tax_data(nsrsbh, cursor):
                    results.append({
                        'nsrsbh': nsrsbh,
                        'status': 'error',
                        'message': 'Failed to insert income tax data'
                    })
                    continue

                results.append({
                    'nsrsbh': nsrsbh,
                    'status': 'success',
                    'message': 'Income tax data processed successfully'
                })

            # 提交事务
            conn.commit()
            app.logger.info('Income tax database transaction committed successfully')

            # 删除上传的文件
            #os.remove(csv_path)

            return jsonify({
                'success': True,
                'processed': len(results),
                'results': results
            }), 200

        except Exception as e:
            conn.rollback()
            app.logger.error(f'Income tax database operation failed: {e}')
            return jsonify({'error': f'Income tax database operation failed: {str(e)}'}), 500

        finally:
            cursor.close()
            conn.close()
            app.logger.info('Income tax database connection closed')

    except Exception as e:
        app.logger.error(f'Unexpected error in income tax CSV processing: {e}')
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/api/import/sql', methods=['POST'])
@login_required
def import_sql_file():
    """SQL文件导入"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        sql_path = os.path.join('uploads', file.filename)
        if not os.path.exists('uploads'):
            os.makedirs('uploads')
        file.save(sql_path)

        conn = get_tax_db_connection()
        cursor = conn.cursor()
        success_count = 0
        errors = []

        try:
            encoding = detect_encoding(sql_path)
            with open(sql_path, 'r', encoding=encoding) as f:
                lines = f.readlines()[3:][:-2]

            sql_commands = ''.join(lines).replace('\n', '').replace(');', ');\n')

            for idx, line in enumerate(sql_commands.split('\n'), 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    cursor.execute(line)
                    success_count += 1
                except Exception as e:
                    errors.append(f"行 {idx}: {str(e)}")

            conn.commit()
            return jsonify({'success': True, 'success_count': success_count, 'errors': errors[:10]}), 200
        except Exception as e:
            conn.rollback()
            return jsonify({'error': str(e)}), 500
        finally:
            cursor.close()
            conn.close()
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/import/folder', methods=['POST'])
@login_required
def import_folder():
    """文件夹导入，自动识别文件类型"""
    try:
        if 'files' not in request.files:
            return jsonify({'error': 'No files uploaded'}), 400

        files = request.files.getlist('files')
        if not files:
            return jsonify({'error': 'No files selected'}), 400

        if not os.path.exists('uploads'):
            os.makedirs('uploads')

        conn = get_tax_db_connection()
        cursor = conn.cursor()
        success_count = 0
        error_count = 0
        details = []

        try:
            for file in files:
                if file.filename == '':
                    continue

                filename = file.filename.lower()
                if filename.endswith('.sql') or filename.endswith('.txt'):
                    file_path = os.path.join('uploads', file.filename)
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    file.save(file_path)

                    try:
                        encoding = detect_encoding(file_path)
                        with open(file_path, 'r', encoding=encoding) as f:
                            lines = f.readlines()[3:][:-2]

                        sql_commands = ''.join(lines).replace('\n', '').replace(');', ');\n')

                        for line in sql_commands.split('\n'):
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                cursor.execute(line)
                                success_count += 1
                            except Exception as e:
                                error_count += 1
                                details.append(f"{file.filename}: {str(e)[:50]}")
                    except Exception as e:
                        error_count += 1
                        details.append(f"{file.filename}: {str(e)[:50]}")

            conn.commit()
            return jsonify({
                'success': True,
                'success_count': success_count,
                'error_count': error_count,
                'details': '\n'.join(details[:10])
            }), 200
        except Exception as e:
            conn.rollback()
            return jsonify({'error': str(e)}), 500
        finally:
            cursor.close()
            conn.close()
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/')
@login_required
def index():
    """主页路由"""
    return render_template('index.html', username=session.get('username', ''))

@app.route('/json-tool')
@login_required
def json_tool():
    """JSON转Excel工具页面"""
    return render_template('Json.html')

@app.route('/api/health', methods=['GET'])
@login_required
def health_check():
    """健康检查端点"""
    try:
        # 检查发票数据库连接
        conn_invoice = get_invoice_db_connection()
        conn_invoice.close()
        
        # 检查税收数据库连接
        conn_tax = get_tax_db_connection()
        conn_tax.close()
        
        return jsonify({
            'status': 'healthy', 
            'invoice_database': 'connected',
            'tax_database': 'connected'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy', 
            'error': str(e)
        }), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # 启动Flask应用
    app.run(host='0.0.0.0', port=8889, debug=True)
    #print(read_csv(r"E:\lk\util\data.csv"))