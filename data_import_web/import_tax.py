# -*- coding: utf-8 -*-
import cx_Oracle
import os
import chardet
import logging

logger = logging.getLogger(__name__)

DB_CONFIG = {
    'user': os.getenv('DB_USER', 'datagrid'),
    'password': os.getenv('DB_PASSWORD', 'datagrid'),
    'host': os.getenv('DB_HOST', '192.168.84.39'),
    'port': os.getenv('DB_PORT', '1521'),
    'service': os.getenv('DB_SERVICE', 'NINVOICE')
}

def get_connection():
    dsn = f"{DB_CONFIG['user']}/{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['service']}"
    return cx_Oracle.connect(dsn)

def detect_encoding(file_path):
    with open(file_path, 'rb') as f:
        raw_data = f.read()
        result = chardet.detect(raw_data)
        encoding = result['encoding'] if result['confidence'] > 0.5 else 'utf-8'
        # GB2312 is a subset of GBK; map it to GBK so extended chars don't cause errors
        encoding_map = {
            'GB2312': 'gbk',
            'GBK': 'gbk',
            'GB18030': 'gb18030',
            'Big5': 'big5',
            'ascii': 'utf-8',
            'ISO-8859-1': 'latin-1',
            'Windows-1252': 'cp1252',
            'UTF-8-SIG': 'utf-8-sig',
        }
        return encoding_map.get(encoding, encoding)


def read_file_with_fallback(file_path):
    """Read a file with encoding detection and automatic fallback."""
    encoding = detect_encoding(file_path)
    fallback_encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb18030', 'latin-1']
    encodings_to_try = [encoding] + [e for e in fallback_encodings if e != encoding]

    for enc in encodings_to_try:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                content = f.read()
            logger.info(f'Read {file_path} with encoding: {enc}')
            return content, enc
        except (UnicodeDecodeError, UnicodeError):
            continue

    raise UnicodeDecodeError(f'无法解码文件 {file_path}，尝试了多种编码')

def _smart_split_sql(text):
    """Split SQL text by semicolons, respecting string literals and to_date(...)."""
    stmts = []
    current = []
    depth = 0          # parenthesis depth
    in_sq = False      # inside single-quoted string
    in_dq = False      # inside double-quoted identifier
    i = 0
    while i < len(text):
        c = text[i]
        if in_sq:
            current.append(c)
            if c == "'" and i + 1 < len(text) and text[i + 1] == "'":
                current.append("'")
                i += 2
                continue
            elif c == "'":
                in_sq = False
        elif in_dq:
            current.append(c)
            if c == '"':
                in_dq = False
        else:
            if c == "'":
                in_sq = True
                current.append(c)
            elif c == '"':
                in_dq = True
                current.append(c)
            elif c == '(':
                depth += 1
                current.append(c)
            elif c == ')':
                depth -= 1
                current.append(c)
            elif c == ';' and depth == 0:
                stmts.append(''.join(current))
                current = []
            else:
                current.append(c)
        i += 1
    remaining = ''.join(current).strip()
    if remaining:
        stmts.append(remaining)
    return stmts


def import_tax_from_file(file_path):
    filename = os.path.basename(file_path)
    conn = get_connection()
    cursor = conn.cursor()

    success_count = 0
    errors = []

    try:
        content, encoding = read_file_with_fallback(file_path)
        logger.info(f'Processing tax file: {file_path} with encoding: {encoding}')

        # 移除 SQL*Plus 命令 (逐行过滤)
        sql_lines = []
        for line in content.split('\n'):
            line_stripped = line.strip()
            line_lower = line_stripped.lower()
            if (not line_lower
                or line_lower.startswith(('prompt', 'set feedback', 'set define', 'set echo', 'commit', 'exit', 'quit'))
                or line_lower == '/'):
                continue
            sql_lines.append(line_stripped)

        # 合并为完整内容并按分号分割（智能分割，考虑字符串内的分号）
        full_content = ' '.join(sql_lines)
        statements = _smart_split_sql(full_content)

        logger.info(f'Found {len(statements)} SQL statements in {filename}')

        for idx, stmt in enumerate(statements, 1):
            stmt = stmt.strip()
            if not stmt or len(stmt) < 10:
                continue

            try:
                cursor.execute(stmt)
                success_count += 1
            except Exception as e:
                error_msg = f"SQL {idx}: {str(e)}"
                errors.append(error_msg)
                logger.error(f'{filename} - {error_msg} | SQL: {stmt[:200]}')

        conn.commit()
        logger.info(f'Tax import completed: {success_count} success, {len(errors)} errors')
        return {
            'success': True,
            'success_count': success_count,
            'errors': errors[:10]
        }
    except Exception as e:
        conn.rollback()
        logger.error(f'Tax import for {filename} failed: {e}')
        return {'success': False, 'error': str(e)}
    finally:
        cursor.close()
        conn.close()
