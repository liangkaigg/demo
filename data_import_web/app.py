# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from functools import wraps
import logging
from logging.handlers import RotatingFileHandler
import os
from flask_cors import CORS
from report_service import report_bp


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
import zipfile
import tempfile
import shutil
import json
import re
from import_invoice import import_invoice_from_file
from import_tax import import_tax_from_file
from invoiceSize.makejson import generate_json, import_invoice_data
from export_tax_excel import export_json_to_excel

# 初始化Flask应用
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24).hex())
CORS(app, supports_credentials=True)

# ==================== 管理员配置 ====================
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'cjx')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'cjx')


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

file_handler = RotatingFileHandler('invoice_service.log', backupCount=10, encoding='utf-8')
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

        conn = get_invoice_db_connection()
        cursor = conn.cursor()

        try:
            if not delete_invoice_data(nsrsbh, cursor):
                return jsonify({'error': 'Failed to delete existing invoice data'}), 500

            if not make_invoice_data(company, nsrsbh, cursor):
                return jsonify({'error': 'Failed to insert/update invoice data'}), 500

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
    """
    try:
        if 'file' not in request.files:
            app.logger.warning('No file uploaded')
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['file']

        if file.filename == '':
            app.logger.warning('No file selected')
            return jsonify({'error': 'No file selected'}), 400

        csv_path = os.path.join('uploads', file.filename)
        if not os.path.exists('uploads'):
            os.makedirs('uploads')
        file.save(csv_path)
        app.logger.info(f'File saved: {csv_path}')

        datas = read_csv(csv_path)

        if not datas:
            return jsonify({'error': 'No valid data found in CSV'}), 400

        app.logger.info(f'Processing {len(datas)} rows from CSV for invoice data')

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

                if not delete_invoice_data(nsrsbh, cursor):
                    results.append({
                        'nsrsbh': nsrsbh,
                        'company': company,
                        'status': 'error',
                        'message': 'Failed to delete existing invoice data'
                    })
                    continue

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

            conn.commit()
            app.logger.info('Invoice database transaction committed successfully')

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
    """处理税收数据的API接口"""
    try:
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

        app.logger.info(f'Processing tax data: nsrsbh={nsrsbh}, company={company}')

        conn = get_tax_db_connection()
        cursor = conn.cursor()

        try:
            if not delete_tax_data(nsrsbh, cursor):
                return jsonify({'error': 'Failed to delete existing tax data'}), 500

            if not make_tax_data(nsrsbh, company, name, zjhm, num, cursor):
                return jsonify({'error': 'Failed to insert tax data'}), 500

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
    """处理CSV文件的API接口 - 税收数据"""
    try:
        if 'file' not in request.files:
            app.logger.warning('No file uploaded')
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['file']

        if file.filename == '':
            app.logger.warning('No file selected')
            return jsonify({'error': 'No file selected'}), 400

        csv_path = os.path.join('uploads', file.filename)
        if not os.path.exists('uploads'):
            os.makedirs('uploads')
        file.save(csv_path)
        app.logger.info(f'File saved: {csv_path}')

        datas = read_csv(csv_path)

        if not datas:
            return jsonify({'error': 'No valid data found in CSV'}), 400

        app.logger.info(f'Processing {len(datas)} rows from CSV for tax data')

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

                if not delete_tax_data(nsrsbh, cursor):
                    results.append({
                        'nsrsbh': nsrsbh,
                        'company': company,
                        'status': 'error',
                        'message': 'Failed to delete existing tax data'
                    })
                    continue

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

            conn.commit()
            app.logger.info('Tax database transaction committed successfully')

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
    """处理出口退税数据的API接口"""
    try:
        data = request.get_json()

        if not data:
            app.logger.warning('No JSON data received')
            return jsonify({'error': 'No JSON data received'}), 400

        nsrsbh = data.get('nsrsbh')

        if not nsrsbh:
            app.logger.warning('Missing nsrsbh in request')
            return jsonify({'error': 'Missing nsrsbh'}), 400

        app.logger.info(f'Processing export tax data: nsrsbh={nsrsbh}')

        conn = get_tax_db_connection()
        cursor = conn.cursor()

        try:
            if not delete_export_tax_data(nsrsbh, cursor):
                return jsonify({'error': 'Failed to delete existing export tax data'}), 500

            if not make_export_tax_data(nsrsbh, cursor):
                return jsonify({'error': 'Failed to insert export tax data'}), 500

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
    """处理CSV文件的API接口 - 出口退税数据"""
    try:
        if 'file' not in request.files:
            app.logger.warning('No file uploaded')
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['file']

        if file.filename == '':
            app.logger.warning('No file selected')
            return jsonify({'error': 'No file selected'}), 400

        csv_path = os.path.join('uploads', file.filename)
        if not os.path.exists('uploads'):
            os.makedirs('uploads')
        file.save(csv_path)
        app.logger.info(f'File saved: {csv_path}')

        datas = read_csv(csv_path)

        if not datas:
            return jsonify({'error': 'No valid data found in CSV'}), 400

        app.logger.info(f'Processing {len(datas)} rows from CSV for export tax data')

        conn = get_tax_db_connection()
        cursor = conn.cursor()

        results = []

        try:
            for data in datas:
                if len(data) < 1:
                    continue

                nsrsbh = data[0]

                app.logger.info(f'Processing export tax data: nsrsbh={nsrsbh}')

                if not delete_export_tax_data(nsrsbh, cursor):
                    results.append({
                        'nsrsbh': nsrsbh,
                        'status': 'error',
                        'message': 'Failed to delete existing export tax data'
                    })
                    continue

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

            conn.commit()
            app.logger.info('Export tax database transaction committed successfully')

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
    """处理所得税数据的API接口"""
    try:
        data = request.get_json()

        if not data:
            app.logger.warning('No JSON data received')
            return jsonify({'error': 'No JSON data received'}), 400

        nsrsbh = data.get('nsrsbh')

        if not nsrsbh:
            app.logger.warning('Missing nsrsbh in request')
            return jsonify({'error': 'Missing nsrsbh'}), 400

        app.logger.info(f'Processing income tax data: nsrsbh={nsrsbh}')

        conn = get_tax_db_connection()
        cursor = conn.cursor()

        try:
            if not delete_income_tax_data(nsrsbh, cursor):
                return jsonify({'error': 'Failed to delete existing income tax data'}), 500

            if not make_income_tax_data(nsrsbh, cursor):
                return jsonify({'error': 'Failed to insert income tax data'}), 500

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
    """处理CSV文件的API接口 - 所得税数据"""
    try:
        if 'file' not in request.files:
            app.logger.warning('No file uploaded')
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['file']

        if file.filename == '':
            app.logger.warning('No file selected')
            return jsonify({'error': 'No file selected'}), 400

        csv_path = os.path.join('uploads', file.filename)
        if not os.path.exists('uploads'):
            os.makedirs('uploads')
        file.save(csv_path)
        app.logger.info(f'File saved: {csv_path}')

        datas = read_csv(csv_path)

        if not datas:
            return jsonify({'error': 'No valid data found in CSV'}), 400

        app.logger.info(f'Processing {len(datas)} rows from CSV for income tax data')

        conn = get_tax_db_connection()
        cursor = conn.cursor()

        results = []

        try:
            for data in datas:
                if len(data) < 1:
                    continue

                nsrsbh = data[0]

                app.logger.info(f'Processing income tax data: nsrsbh={nsrsbh}')

                if not delete_income_tax_data(nsrsbh, cursor):
                    results.append({
                        'nsrsbh': nsrsbh,
                        'status': 'error',
                        'message': 'Failed to delete existing income tax data'
                    })
                    continue

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

            conn.commit()
            app.logger.info('Income tax database transaction committed successfully')

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

@app.route('/api/import/zip', methods=['POST'])
@login_required
def import_zip():
    """ZIP文件导入 — 自动识别发票和税务SQL文件"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['file']
        if file.filename == '' or not file.filename.lower().endswith('.zip'):
            return jsonify({'error': 'Please upload a ZIP file'}), 400

        zip_path = os.path.join('uploads', file.filename)
        if not os.path.exists('uploads'):
            os.makedirs('uploads')
        file.save(zip_path)
        app.logger.info(f'ZIP saved: {zip_path}')

        extract_dir = tempfile.mkdtemp(prefix='zip_import_')
        app.logger.info(f'Extracting to: {extract_dir}')

        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(extract_dir)

            sql_files = []
            for root, dirs, filenames in os.walk(extract_dir):
                for fname in filenames:
                    if fname.lower().endswith(('.sql', '.txt')):
                        sql_files.append(os.path.join(root, fname))

            app.logger.info(f'Found {len(sql_files)} SQL files in ZIP')

            total_files = len(sql_files)
            invoice_success = 0
            invoice_skip = 0
            tax_success = 0
            all_errors = []

            invoice_keywords = ['invoice', 'item', '发票', '0238']

            for sql_file in sql_files:
                basename = os.path.basename(sql_file).lower()
                is_invoice = any(kw in basename for kw in invoice_keywords)

                if is_invoice:
                    app.logger.info(f'Processing invoice file: {basename}')
                    result = import_invoice_from_file(sql_file)
                    if result['success']:
                        invoice_success += result['success_count']
                        invoice_skip += result.get('skip_count', 0)
                        if result.get('errors'):
                            all_errors.extend(result['errors'])
                    else:
                        all_errors.append(f"{os.path.basename(sql_file)}: {result.get('error', 'Unknown error')}")
                else:
                    app.logger.info(f'Processing tax file: {basename}')
                    result = import_tax_from_file(sql_file)
                    if result['success']:
                        tax_success += result['success_count']
                        if result.get('errors'):
                            all_errors.extend(result['errors'])
                    else:
                        all_errors.append(f"{os.path.basename(sql_file)}: {result.get('error', 'Unknown error')}")

            app.logger.info(f'ZIP import finished: invoice={invoice_success}/{invoice_skip}, tax={tax_success}, errors={len(all_errors)}')

            return jsonify({
                'success': True,
                'total_files': total_files,
                'invoice_success': invoice_success,
                'invoice_skip': invoice_skip,
                'tax_success': tax_success,
                'errors': all_errors[:20]
            }), 200

        finally:
            shutil.rmtree(extract_dir, ignore_errors=True)
            try:
                os.remove(zip_path)
            except Exception:
                pass

    except zipfile.BadZipFile:
        return jsonify({'error': 'Invalid ZIP file'}), 400
    except Exception as e:
        app.logger.error(f'ZIP import failed: {e}')
        return jsonify({'error': f'Import failed: {str(e)}'}), 500


@app.route('/api/import/delete', methods=['POST'])
@login_required
def delete_data():
    """批量删除纳税人数据"""
    try:
        data = request.get_json()
        if not data or 'nsrsbh_list' not in data:
            return jsonify({'error': 'Missing nsrsbh_list'}), 400

        nsrsbh_text = data['nsrsbh_list'].strip()
        if not nsrsbh_text:
            return jsonify({'error': 'No taxpayer IDs provided'}), 400

        ids = re.split(r'[,，\s\n\r]+', nsrsbh_text)
        ids = [id.strip() for id in ids if id.strip()]

        app.logger.info(f'Deleting data for {len(ids)} taxpayers: {ids[:5]}...')

        conn_invoice = get_invoice_db_connection()
        conn_tax = get_tax_db_connection()
        cursor_inv = conn_invoice.cursor()
        cursor_tax = conn_tax.cursor()

        success_count = 0
        failed_list = []

        try:
            for nsrsbh in ids:
                try:
                    delete_invoice_data(nsrsbh, cursor_inv)
                    delete_tax_data(nsrsbh, cursor_tax)
                    delete_export_tax_data(nsrsbh, cursor_tax)
                    delete_income_tax_data(nsrsbh, cursor_tax)
                    success_count += 1
                except Exception as e:
                    failed_list.append(f"{nsrsbh}: {str(e)}")
                    app.logger.error(f'Delete failed for {nsrsbh}: {e}')

            conn_invoice.commit()
            conn_tax.commit()

            msg = f"成功删除 {success_count} 个税号的数据"
            if failed_list:
                msg += f"\n失败 ({len(failed_list)}):\n" + '\n'.join(failed_list[:10])

            return jsonify({
                'success': True,
                'message': msg
            }), 200

        except Exception as e:
            conn_invoice.rollback()
            conn_tax.rollback()
            app.logger.error(f'Delete transaction failed: {e}')
            return jsonify({'error': str(e)}), 500
        finally:
            cursor_inv.close()
            cursor_tax.close()
            conn_invoice.close()
            conn_tax.close()

    except Exception as e:
        app.logger.error(f'Delete data failed: {e}')
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

@app.route('/api/tax/export', methods=['POST'])
@login_required
def export_tax_excel_api():
    """将税务标准JSON文件导出为Excel（与模板格式一致）"""
    try:
        import uuid
        if not os.path.exists('uploads'):
            os.makedirs('uploads')

        # Accept file upload or raw JSON body
        if request.is_json:
            data = request.get_json()
            file_id = uuid.uuid4().hex[:8]
            json_path = os.path.join('uploads', f'tax_export_{file_id}.json')
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            output_filename = f'tax_export_{file_id}.xlsx'
        elif 'file' in request.files:
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            json_path = os.path.join('uploads', file.filename)
            file.save(json_path)
            output_filename = file.filename.rsplit('.', 1)[0] + '.xlsx'
        else:
            return jsonify({'error': 'No JSON data or file provided'}), 400

        output_path = os.path.join('uploads', output_filename)
        export_json_to_excel(json_path, output_path)

        from flask import send_file
        response = send_file(
            output_path,
            as_attachment=True,
            download_name=output_filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        # Clean up temp files after response
        @response.call_on_close
        def cleanup():
            try:
                if os.path.exists(json_path):
                    os.remove(json_path)
                if os.path.exists(output_path):
                    os.remove(output_path)
            except Exception:
                pass

        return response
    except json.JSONDecodeError as e:
        return jsonify({'error': f'Invalid JSON file: {str(e)}'}), 400
    except Exception as e:
        app.logger.error(f'Tax export failed: {e}')
        return jsonify({'error': f'Export failed: {str(e)}'}), 500

@app.route('/api/health', methods=['GET'])
@login_required
def health_check():
    """健康检查端点"""
    try:
        conn_invoice = get_invoice_db_connection()
        conn_invoice.close()

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

@app.route('/api/invoice/generate', methods=['POST'])
@login_required
def generate_invoice():
    """发票数据生成与入库"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data received'}), 400

        name = data.get('name', '').strip()
        tax_no = data.get('tax_no', '').strip()
        size_mb = data.get('size_mb', 10)

        if not tax_no or not name:
            return jsonify({'error': '税号和企业名称不能为空'}), 400

        size_mb = float(size_mb)
        if size_mb <= 0:
            return jsonify({'error': '文件大小必须大于0'}), 400

        app.logger.info(f'Generating invoice JSON: tax_no={tax_no}, name={name}, size={size_mb}MB')

        target_size = int(size_mb * 1024 * 1024)
        output_file = os.path.join('uploads', f'invoice_gen_{tax_no}.json')

        # Step 1: 生成JSON文件
        if not os.path.exists('uploads'):
            os.makedirs('uploads')
        count, final_size = generate_json(output_file, name, tax_no, target_size)

        # Step 2: 导入数据库
        import_invoice_data(output_file)

        # 清理临时文件
        try:
            os.remove(output_file)
        except Exception:
            pass

        return jsonify({
            'success': True,
            'message': f'发票数据生成并入库成功',
            'records': count,
            'file_size_mb': round(final_size / 1024 / 1024, 2),
            'company': name,
            'tax_no': tax_no
        }), 200

    except Exception as e:
        app.logger.error(f'Invoice generation failed: {e}')
        return jsonify({'error': f'生成失败: {str(e)}'}), 500



# URL前缀中间件 - 所有路由添加 /jx 前缀
class PrefixMiddleware:
    def __init__(self, app, prefix='/jx'):
        self.app = app
        self.prefix = prefix

    def __call__(self, environ, start_response):
        if environ['PATH_INFO'].startswith(self.prefix):
            environ['PATH_INFO'] = environ['PATH_INFO'][len(self.prefix):]
            environ['SCRIPT_NAME'] = self.prefix
            return self.app(environ, start_response)
        start_response('404 Not Found', [('Content-Type', 'text/plain')])
        return [b'Not Found']

app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix='/jx')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8889, debug=True)
