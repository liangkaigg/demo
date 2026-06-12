# -*- coding: utf-8 -*-
import cx_Oracle
import os
import re
import chardet

DB_CONFIG = {
    'user': os.getenv('DB_USER', 'datagrid'),
    'password': os.getenv('DB_PASSWORD', 'datagrid'),
    'host': os.getenv('DB_HOST', '192.168.85.64'),
    'port': os.getenv('DB_PORT', '1521'),
    'service': os.getenv('DB_SERVICE', 'emserver')
}

INSERT_INVOICE = """INSERT INTO DATAGRID.INVOICE_GENERAL_0238(
    INVOICE_MACHINE, MACHINE_NO, INVOICE_CODE, INVOICE_NUMBER, BILLING_DATE, INVOICE_TYPE, DATA_TYPE,
    CHECK_CODE, INVOICE_STATE, AMOUNT_TAX, PURCHASER, PURCHASE_BANK, PURCHASE_ADDRESS, PURCHASE_MOBILE,
    SALER, SALE_BANK, SALE_ADDRESS, SALE_MOBILE, TOTAL_AMOUNT, TOTAL_TAX, REMARK, PASSWORD, DRAWER,
    REVIEWER, PAYEE, SALE_TAX_CODE, TAX_RATE, TAX, INVOICE_SRC, DEDUCTIBLE, DEDUCTIBLE_PERIOD,
    DEDUCTIBLE_DATE, DEDUCTIBLE_TYPE, DEDUCTIBLE_MODE, CLIENT_NSRSBH, CREATE_TIME, TICKET_ID, YEARMONTH,
    PURCHASE_TAX_CODE, UPDATE_TIME, ID, BILLING_DATETIME
) VALUES (
    :1,:2,:3,:4,TO_DATE(:5,'DD-MM-YYYY'),:6,:7,:8,:9,:10,:11,:12,:13,:14,:15,:16,:17,:18,:19,:20,
    :21,:22,:23,:24,:25,:26,:27,:28,:29,:30,:31,:32,:33,:34,:35,TO_DATE(:36,'dd-mm-yyyy hh24:mi:ss'),
    :37,:38,:39,TO_DATE(:40,'dd-mm-yyyy hh24:mi:ss'),:41,TO_DATE(:42,'dd-mm-yyyy hh24:mi:ss')
)"""

INSERT_ITEM = """INSERT INTO invoice_item_0238 (
    ID, ROW_NO, UNIT_PRICE, AMOUNT, TAX_RATE, QUANTITY, TAX_CLASSIFY_CODE, COMMODITY_NAME,
    SPECIFICATION_MODEL, UNIT, TAX, CAR_NUMBER, START_DATE, END_DATE, INVOICE_NUMBER, INVOICE_CODE,
    INVOICE_ID, INVOICE_TYPE, BILLING_DATE, DATA_TYPE, STATE, PURCHASER_NAME, SALES_NAME, SALES_TAX_NO,
    DATA_NSRSBH, CREATE_TIME, PURCHASER_TAX_NO, BILLING_DATETIME
) VALUES (
    :1,:2,:3,:4,:5,:6,:7,:8,:9,:10,:11,:12,:13,:14,:15,:16,:17,:18,TO_DATE(:19,'DD-MM-YYYY'),
    :20,:21,:22,:23,:24,:25,TO_DATE(:26,'dd-mm-yyyy hh24:mi:ss'),:27,TO_DATE(:28,'dd-mm-yyyy hh24:mi:ss')
)"""

def get_connection():
    dsn = f"{DB_CONFIG['user']}/{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['service']}"
    return cx_Oracle.connect(dsn)

def extract_values_content(sql_text):
    results = []
    for match in re.finditer(r'values\s*\(', sql_text, re.IGNORECASE):
        paren_start = match.end() - 1
        depth = 1
        j = paren_start + 1
        in_quotes = False

        while j < len(sql_text) and depth > 0:
            c = sql_text[j]
            if c == "'" and not in_quotes:
                in_quotes = True
            elif c == "'" and in_quotes:
                if j + 1 < len(sql_text) and sql_text[j + 1] == "'":
                    j += 1
                else:
                    in_quotes = False
            elif not in_quotes:
                if c == '(':
                    depth += 1
                elif c == ')':
                    depth -= 1
            j += 1

        if depth == 0:
            results.append(sql_text[paren_start + 1:j - 1])

    return results

def parse_complex_string(s):
    s = s.strip()
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1]

    fields = []
    current_field = []
    in_quotes = False
    i = 0

    while i < len(s):
        char = s[i]

        if in_quotes:
            current_field.append(char)
            if char == "'" and i + 1 < len(s) and s[i + 1] == "'":
                current_field.append("'")
                i += 2
                continue
            elif char == "'":
                in_quotes = False
            i += 1
        else:
            if char == "'":
                in_quotes = True
                current_field.append(char)
                i += 1
            elif char == ',':
                field_str = ''.join(current_field).strip()
                if field_str or len(fields) > 0:
                    fields.append(field_str if field_str else 'null')
                current_field = []
                i += 1
            elif char in ' \t':
                if current_field:
                    current_field.append(char)
                i += 1
            else:
                current_field.append(char)
                i += 1

    field_str = ''.join(current_field).strip()
    if field_str or len(fields) > 0:
        fields.append(field_str if field_str else 'null')

    return fields

def parse_values_to_tuple(content):
    # 清理多余引号和括号（正则替换）
    content = re.sub(r'^"|"$', '', content)
    content = re.sub(r'^\[|\]$', '', content)
    content = parse_complex_string(content)

    parsed = []
    for elem in content:
        elem = elem.strip()
        if not elem or elem.lower() == 'null':
            parsed.append(None)
            continue

        if (elem.startswith("'") and elem.endswith("'")) or \
           (elem.startswith('"') and elem.endswith('"')):
            inner = elem[1:-1]
            inner = inner.replace('\\"', '"').replace("\\'", "'")
            parsed.append(inner)
        else:
            if 'e' in elem.lower():
                try:
                    parsed.append(float(elem))
                    continue
                except ValueError:
                    pass

            try:
                num = float(elem)
                parsed.append(int(num) if num.is_integer() else num)
            except ValueError:
                parsed.append(elem if elem else None)

    return tuple(parsed)

def detect_encoding(file_path):
    with open(file_path, 'rb') as f:
        raw_data = f.read()
        result = chardet.detect(raw_data)
        encoding = result['encoding'] if result and result['encoding'] and result['confidence'] > 0.5 else 'utf-8'
        # GB2312 is a subset of GBK; map it to GBK so extended chars don't cause errors
        encoding_map = {
            'GB2312': 'gbk',
            'GBK': 'gbk',
            'GB18030': 'gb18030',
            'Big5': 'big5',
            'ascii': 'utf-8',
            'ISO-8859-1': 'latin-1',
            'Windows-1252': 'cp1252',
        }
        return encoding_map.get(encoding, encoding)

def process_sql_file(file_path):
    encoding = detect_encoding(file_path)
    # Try fallback encodings if primary fails
    fallback_encodings = ['utf-8', 'gbk', 'gb18030', 'latin-1']
    encodings_to_try = [encoding] + [e for e in fallback_encodings if e != encoding]

    lines = None
    for enc in encodings_to_try:
        try:
            with open(file_path, 'r', encoding=enc) as file:
                lines = file.readlines()
            break
        except (UnicodeDecodeError, UnicodeError):
            continue

    if lines is None:
        raise UnicodeDecodeError('无法解码文件，尝试了多种编码: ' + ', '.join(encodings_to_try))

    # 过滤SQL*Plus命令
    filtered_lines = [line for line in lines if not re.match(r'^\s*(prompt|set\s+)', line, re.IGNORECASE)]
    content = ''.join(filtered_lines)

    matches = extract_values_content(content)

    results = []
    for match in matches:
        processed = re.sub(r"to_date\('([^']+(?:''[^']*)*)',\s*'[^']+'\)", r"'\1'", match, flags=re.IGNORECASE)
        results.append((match, parse_values_to_tuple(processed)))

    return results

BATCH_SIZE = 500


def import_invoice_from_file(file_path):
    conn = get_connection()
    cursor = conn.cursor()

    success_count = 0
    skip_count = 0
    errors = []

    try:
        results = process_sql_file(file_path)
        is_item = 'item' in os.path.basename(file_path).lower()
        sql_template = INSERT_ITEM if is_item else INSERT_INVOICE
        expected_params = len(re.findall(r':\d+', sql_template))

        # 收集所有数据行，统一处理参数长度
        all_tuples = []
        for idx, (original_sql, data_tuple) in enumerate(results, 1):
            if len(data_tuple) != expected_params:
                if len(data_tuple) < expected_params:
                    data_tuple = data_tuple + (None,) * (expected_params - len(data_tuple))
                else:
                    skip_count += 1
                    errors.append(f"记录 {idx}: 参数不匹配 (期望{expected_params}, 实际{len(data_tuple)})")
                    continue
            all_tuples.append(data_tuple)

        # 批量插入
        for i in range(0, len(all_tuples), BATCH_SIZE):
            batch = all_tuples[i:i + BATCH_SIZE]
            try:
                cursor.executemany(sql_template, batch, batcherrors=True)
                batch_errors = cursor.getbatcherrors()
                for err in batch_errors:
                    errors.append(f"记录 {i + err.offset + 1}: {err.message}")
                success_count += len(batch) - len(batch_errors)
            except Exception as e:
                errors.append(f"批量插入错误 (行{i+1}-{i+len(batch)}): {str(e)}")

        conn.commit()
        return {
            'success': True,
            'total': len(results),
            'success_count': success_count,
            'skip_count': skip_count,
            'errors': errors[:10]
        }
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        cursor.close()
        conn.close()
