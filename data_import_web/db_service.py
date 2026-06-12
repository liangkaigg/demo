# -*- coding: utf-8 -*-
"""共享数据库服务模块 - 包含所有业务逻辑和数据访问函数"""
import cx_Oracle
import os
import csv
import logging
import chardet

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# 发票数据库配置
INVOICE_DB_CONFIG = {
    'user': os.getenv('DB_USER', 'datagrid'),
    'password': os.getenv('DB_PASSWORD', 'datagrid'),
    'dsn': os.getenv('INVOICE_DB_DSN', '192.168.85.64:1521/emserver')
}

# 税收数据库配置
TAX_DB_CONFIG = {
    'user': os.getenv('DB_USER', 'datagrid'),
    'password': os.getenv('DB_PASSWORD', 'datagrid'),
    'dsn': os.getenv('TAX_DB_DSN', '192.168.84.39:1521/ninvoice')
}


def get_invoice_db_connection():
    """创建发票数据库连接"""
    try:
        connection = cx_Oracle.connect(
            user=INVOICE_DB_CONFIG['user'],
            password=INVOICE_DB_CONFIG['password'],
            dsn=INVOICE_DB_CONFIG['dsn']
        )
        logger.info('Invoice database connection established')
        return connection
    except cx_Oracle.Error as e:
        logger.error(f'Invoice database connection failed: {e}')
        raise


def get_tax_db_connection():
    """创建税收数据库连接"""
    try:
        connection = cx_Oracle.connect(
            user=TAX_DB_CONFIG['user'],
            password=TAX_DB_CONFIG['password'],
            dsn=TAX_DB_CONFIG['dsn']
        )
        logger.info('Tax database connection established')
        return connection
    except cx_Oracle.Error as e:
        logger.error(f'Tax database connection failed: {e}')
        raise


def detect_encoding(file_path, sample_size=10000):
    """检测文件编码"""
    try:
        with open(file_path, 'rb') as file:
            raw_data = file.read(sample_size)
            if not raw_data:
                return 'utf-8'
            result = chardet.detect(raw_data)
            encoding = result.get('encoding')
            confidence = result.get('confidence', 0)
            logger.debug("检测到编码: %s, 置信度: %s", encoding, confidence)
            if not encoding or confidence < 0.5:
                return 'utf-8'
            encoding_map = {
                'GB2312': 'gbk', 'GBK': 'gbk', 'GB18030': 'gb18030',
                'Big5': 'big5', 'ascii': 'utf-8', 'ISO-8859-1': 'latin-1',
                'Windows-1252': 'cp1252', 'Windows-1251': 'cp1251',
                'SHIFT_JIS': 'shift_jis', 'EUC-JP': 'euc_jp',
            }
            return encoding_map.get(encoding, encoding)
    except Exception as e:
        logger.warning("编码检测失败: %s，使用默认编码utf-8", str(e))
        return 'utf-8'


def read_csv(csv_path, column1_idx=0, column2_idx=1, has_header=False,
             delimiter=',', encoding=None, fallback_encodings=None):
    """读取CSV文件（支持自动编码检测）"""
    result = []
    if fallback_encodings is None:
        fallback_encodings = ['utf-8', 'gbk', 'latin-1', 'cp1252']
    try:
        if encoding is None:
            encoding = detect_encoding(csv_path)
        encodings_to_try = [encoding] + fallback_encodings
        file_opened = False
        for enc in encodings_to_try:
            try:
                with open(csv_path, 'r', encoding=enc) as file:
                    reader = csv.reader(file, delimiter=delimiter)
                    if has_header:
                        try:
                            next(reader)
                        except StopIteration:
                            logger.warning("文件 %s 为空", csv_path)
                            return result
                    row_num_offset = 1 if has_header else 0
                    for row_num, row in enumerate(reader, start=row_num_offset):
                        if not row:
                            continue
                        if len(row) < max(column1_idx, column2_idx) + 1:
                            logger.warning("第 %s 行数据不足，跳过该行", row_num + 1)
                            continue
                        col1 = row[column1_idx].strip() if column1_idx < len(row) else ''
                        col2 = row[column2_idx].strip() if column2_idx < len(row) else ''
                        result.append((col1, col2))
                    logger.info('成功从 %s 读取 %s 行数据，使用编码: %s',
                               csv_path, len(result), enc)
                    file_opened = True
                    break
            except UnicodeDecodeError:
                logger.debug("编码 %s 解码失败，尝试下一个编码", enc)
                continue
            except Exception as e:
                logger.error("使用编码 %s 读取文件时发生错误: %s", enc, str(e))
                if not file_opened and enc == encodings_to_try[-1]:
                    raise
        if not result:
            logger.warning("文件 %s 没有读取到有效数据", csv_path)
        return result
    except IOError as e:
        if "No such file" in str(e):
            logger.error("文件 %s 未找到", csv_path)
            raise IOError("文件未找到: " + csv_path)
        else:
            logger.error("读取文件 %s 时发生IO错误: %s", csv_path, str(e))
            raise
    except Exception as e:
        logger.error("读取文件时发生错误: %s", str(e))
        raise


# ==================== 发票数据处理函数 ====================

def delete_invoice_data(nsrsbh, cursor):
    """删除指定纳税人的发票数据"""
    try:
        sql_1 = f"DELETE FROM INVOICE_GENERAL_0238 WHERE CLIENT_NSRSBH = '{nsrsbh}'"
        sql_2 = f"DELETE FROM invoice_item_0238 WHERE DATA_NSRSBH = '{nsrsbh}'"
        logger.info(f'Executing: {sql_1}')
        cursor.execute(sql_1)
        logger.info(f'Executing: {sql_2}')
        cursor.execute(sql_2)
        return True
    except Exception as e:
        logger.error(f'Error deleting invoice data: {e}')
        return False


def make_invoice_data(company, nsrsbh, cursor):
    """插入发票数据"""
    try:
        invoice_sql = f"""
        INSERT INTO INVOICE_GENERAL_0238
        SELECT INVOICE_MACHINE, MACHINE_NO, INVOICE_CODE, INVOICE_NUMBER, BILLING_DATE,
               INVOICE_TYPE, DATA_TYPE, CHECK_CODE, INVOICE_STATE, AMOUNT_TAX,
               PURCHASER, PURCHASE_BANK, PURCHASE_ADDRESS, PURCHASE_MOBILE,
               SALER, SALE_BANK, SALE_ADDRESS, SALE_MOBILE, TOTAL_AMOUNT,
               TOTAL_TAX, REMARK, PASSWORD, DRAWER, REVIEWER, PAYEE,
               SALE_TAX_CODE, TAX_RATE, TAX, INVOICE_SRC, DEDUCTIBLE,
               DEDUCTIBLE_PERIOD, DEDUCTIBLE_DATE, DEDUCTIBLE_TYPE,
               DEDUCTIBLE_MODE, '{nsrsbh}', CREATE_TIME, TICKET_ID, YEARMONTH,
               PURCHASE_TAX_CODE, UPDATE_TIME, ID, BILLING_DATETIME
        FROM DATAGRID.INVOICE_GENERAL_0238
        WHERE CLIENT_NSRSBH = '91440300691191423W'
        """
        invoice_item_sql = f"""
        INSERT INTO invoice_item_0238
        SELECT ID, ROW_NO, UNIT_PRICE, AMOUNT, TAX_RATE, QUANTITY,
               TAX_CLASSIFY_CODE, COMMODITY_NAME, SPECIFICATION_MODEL,
               UNIT, TAX, CAR_NUMBER, START_DATE, END_DATE, INVOICE_NUMBER,
               INVOICE_CODE, INVOICE_ID, INVOICE_TYPE, BILLING_DATE,
               DATA_TYPE, STATE, PURCHASER_NAME, SALES_NAME, SALES_TAX_NO,
               '{nsrsbh}', CREATE_TIME, PURCHASER_TAX_NO, BILLING_DATETIME
        FROM DATAGRID.INVOICE_ITEM_0238
        WHERE DATA_NSRSBH = '91440300691191423W'
        """
        update_purchaser = f"""
        UPDATE invoice_general_0238
        SET PURCHASER = '{company}', PURCHASE_TAX_CODE = '{nsrsbh}'
        WHERE CLIENT_NSRSBH = '{nsrsbh}' AND DATA_TYPE = '1'
        """
        update_sale = f"""
        UPDATE invoice_general_0238
        SET SALER = '{company}', SALE_TAX_CODE = '{nsrsbh}'
        WHERE CLIENT_NSRSBH = '{nsrsbh}' AND DATA_TYPE = '2'
        """
        sql_list = [invoice_sql, invoice_item_sql, update_purchaser, update_sale]
        for sql in sql_list:
            logger.info(f'Executing: {sql}')
            cursor.execute(sql)
        return True
    except Exception as e:
        logger.error(f'Error making invoice data: {e}')
        return False


# ==================== 税收数据处理函数 ====================

def delete_tax_data(nsrsbh, cursor, flag=False):
    """删除指定纳税人的税收数据"""
    try:
        table_list = ["ZX_LRBXX", "ZX_SBXX", "ZX_ZCFZBXX", "ZX_LXRXX", "ZX_BGDJXX",
                     "ZX_NSRJCXX", "ZX_SBZSXX", "ZX_TZFXX", "ZX_WFWZXX", "ZX_JCAJXX"]
        for table in table_list:
            sql = f"DELETE FROM {table} WHERE NSRSBH = '{nsrsbh}'"
            logger.info(f'Executing: {sql}')
            cursor.execute(sql)
        cursor.connection.commit()
        logger.info(f'Tax data deleted for nsrsbh: {nsrsbh}')
        return True
    except Exception as e:
        logger.error(f'Error deleting tax data: {e}')
        return False


def make_tax_data(nsrsbh, company, name=None, zjhm=None, num=10000, cursor=None):
    """插入税收数据"""
    try:
        batch_id = nsrsbh
        sql_lrb = f"""
        INSERT INTO ZX_LRBXX
        SELECT ID_LRB, XH, sysdate, XMLMC, '{nsrsbh}', NSRMC, BSRQ, SKSSQQ, SKSSQZ, XM, MC, BQJE, SQJE, BYS, TICKET, '{batch_id}'
        FROM DATAGRID.ZX_LRBXX
        WHERE NSRSBH = '9113070078982791X7' AND rownum < {num}
        """
        sql_sbxx = f"""
        INSERT INTO ZX_SBXX
        SELECT ID_SBXX, sysdate, '{nsrsbh}', SBRQ, ZSXMDM, ZSXMMC, SSSQQ, SSSQZ, QBXSE, YSXSSR, YNSE, YJSE, YBTSE, JMSE, JMSR, MSXSE, CKMSXSE, CKMDTXSE, SBQX, YXBZ, TICKET, '{batch_id}', PCH, GZLX_DM
        FROM DATAGRID.ZX_SBXX
        WHERE NSRSBH = '9113070078982791X7' AND SSSQZ >= TO_CHAR(TRUNC(SYSDATE - 2 * 365, 'YYYY'), 'YYYY-MM-DD') AND rownum < {num}
        """
        sql_zcfz = f"""
        INSERT INTO ZX_ZCFZBXX
        SELECT ID_ZCFZB, XH, sysdate, XMLMC, '{nsrsbh}', NSRMC, BSRQ, SKSSQQ, SKSSQZ, XM, MC, QMYE, NCYE, TICKET, '{batch_id}', COLUMN1, ZXPM_DM, YXBZ, CZLX_DM, CZLXMC, TZLX_DM, TZLXMC, SKCLLX_DM, SKCLLXMC
        FROM DATAGRID.ZX_ZCFZBXX
        WHERE NSRSBH = '9113070078982791X7' AND rownum < {num}
        """
        if name is not None:
            sql_lxrxx = f"""
            INSERT INTO ZX_LXRXX
            SELECT ID_LXR, sysdate, '{nsrsbh}', NSRMC, '{name}', DBR_DHHM, DBR_YDDHHM, DBR_DYDZ, DBR_ZJLX_DM, DBR_ZJLX_MC, '{zjhm}', BSSF, KEYVERSION, TICKET, '{batch_id}'
            FROM DATAGRID.ZX_LXRXX
            WHERE NSRSBH = '9113070078982791X7' AND rownum <= 1
            """
        else:
            sql_lxrxx = f"""
            INSERT INTO ZX_LXRXX
            SELECT ID_LXR, sysdate, '{nsrsbh}', NSRMC, DBRMC, DBR_DHHM, DBR_YDDHHM, DBR_DYDZ, DBR_ZJLX_DM, DBR_ZJLX_MC, DBR_ZJHM, BSSF, KEYVERSION, TICKET, '{batch_id}'
            FROM DATAGRID.ZX_LXRXX
            WHERE NSRSBH = '9113070078982791X7' AND rownum <= 1
            """
        sql_bgdj = f"""
        INSERT INTO ZX_BGDJXX
        SELECT ID_BGXX, sysdate, '{nsrsbh}', NSRMC, BGXMMC, BGQNR, BGHNR, BGRQ, BGXMDM, TICKET, '{batch_id}'
        FROM DATAGRID.ZX_BGDJXX
        WHERE NSRSBH = '91620403MABT01MB6T' AND rownum < {num}
        """
        sql_nsrjcxx = f"""
        INSERT INTO ZX_NSRJCXX
        SELECT ID_QY, '{nsrsbh}', '{company}', ZCDZ, YYDZ, DHHM, YB, QYHGDM, SSHYDM, SSHYMC, DJZCLXDM, DJZCLXMC, NSLXDM, NSLXMC, XYDJ, GSZCH, SCJYQX_Z, ZCZB, SYKJZD, SYKJZDMC, LSGXDM, LSGXMC, NSRZTDM, NSRZTMC, SWJG_DM, SWJG_MC, ZGY, sysdate, KYRQ, ZCZBBZ, ZYRS, JYFW, XYPFSJ, XYPFFS, ZCD_DHHM, ZCZB_BZMC, ZZJGDM, HZDJRQ, KEYVERSION, TICKET, '{batch_id}'
        FROM DATAGRID.ZX_NSRJCXX
        WHERE NSRSBH = '9113070078982791X7' AND rownum <= 1
        """
        sql_sbzf = f"""
        INSERT INTO ZX_SBZSXX
        SELECT ZS_ID, SSSQ_Q, SSSQ_Z, JKQX, JKFSRQ, ZSXM_MC, SKZL_MC, SKZT_MC, XSSR, SL, SE, sysdate, '{nsrsbh}', ZXPM_DM, YXBZ, CZLX_DM, CZLXMC, TZLX_DM, TZLXMC, SKCLLX_DM, SKCLLXMC, TICKET, '{batch_id}', ZSXM_DM, SKZL_DM, SKZT_DM
        FROM DATAGRID.ZX_SBZSXX
        WHERE NSRSBH = '9113070078982791X7' AND rownum < {num}
        """
        sql_tzf = f"""
        INSERT INTO ZX_TZFXX
        SELECT ID_TZF, sysdate, '{nsrsbh}', NSRMC, TZFMC, TZFJJXZDM, TZFJJXZMC, TZBL, ZJZLDM, ZJZLMC, ZJHM, GJDZ, TZJE, KEYVERSION, TICKET, '{batch_id}'
        FROM DATAGRID.ZX_TZFXX
        WHERE NSRSBH = '9113070078982791X7' AND rownum < {num}
        """
        sql_wfwz = f"""
        INSERT INTO ZX_WFWZXX
        SELECT ID_WFWZ, sysdate, '{nsrsbh}', DJRQ, ZYWFWZSS, ZYWFWZSDDM, ZYWFWZSDMC, WFWZLXDM, WFWZLXMC, WFWZZTDM, WFWZZTMC, CLCFJDRQ, CLBF, LARQ, XGZT, TICKET, '{batch_id}'
        FROM DATAGRID.ZX_WFWZXX
        WHERE NSRSBH = '91320585MACPF9AG2B' AND DJRQ >= TO_CHAR(TRUNC(SYSDATE - 2 * 365, 'YYYY'), 'YYYY') AND rownum < {num}
        """
        sql_jcaj = f"""
        INSERT INTO ZX_JCAJXX
        SELECT ID_JCAJ, sysdate, '{nsrsbh}', AYDJRQ, AJLYDM, AJLYMC, WFWZLXDM, WFWZLXMC, JCLXDM, JCLXMC, JCZTDM, JCZTMC, AJCLYJDM, AJCLYJMC, AJMC, TICKET, '{batch_id}'
        FROM DATAGRID.ZX_JCAJXX
        WHERE NSRSBH = '9133020679008392XR' AND AYDJRQ >= TO_CHAR(TRUNC(SYSDATE - 3 * 365, 'YYYY'), 'YYYY') AND rownum < {num}
        """
        sql_list = [sql_lrb, sql_sbxx, sql_lxrxx, sql_bgdj, sql_nsrjcxx, sql_sbzf, sql_tzf, sql_wfwz, sql_jcaj, sql_zcfz]
        batch_sql = f"INSERT INTO T_SJZLJC_RZ_LEVEL@to_jrwz2_zx (BANKID, NSRSBH, NSRMC, LEVEL_DJ, LRSJ, SOURCE, REMARK, SOURCE_CODE, BATCH_ID) VALUES ('WZX01', '{nsrsbh}', NULL, 'T', SYSDATE+30, '电子税务', NULL, '1', '{batch_id}')"
        cursor.execute(f"DELETE FROM T_SJZLJC_RZ_LEVEL@to_jrwz2_zx WHERE NSRSBH = '{nsrsbh}'")
        cursor.execute(batch_sql)
        for sql in sql_list:
            logger.info(f'Executing tax SQL: {sql}')
            cursor.execute(sql)
        return True
    except Exception as e:
        logger.error(f'Error making tax data: {e}')
        return False


# ==================== 所得税数据处理函数 ====================

def delete_income_tax_data(nsrsbh, cursor):
    """删除指定纳税人的所得税数据"""
    try:
        table_list = [
            "SZ_QYSDS_JCXX", "SZ_QYSDS_JDSBB", "SZ_QYSDS_NDSBB", "SZ_QYSDS_GZXJ",
            "SZ_QYSDS_QJFYMXB", "SZ_QYSDS_ZCZJ", "SZ_YAFY_YHMXB", "ZX_QYSDS_SRMXB",
            "ZX_WAQZFSZ_SRNSTZMXB", "ZX_ZCSSSQKC_NSTZMXB", "SZ_GXQY_YHMXB_ZDZCLY",
            "ZX_ZXYTCZXZJ_NSTZMXB", "SZ_GXQY_YHMXB", "SZ_QYSDS_NDSBB",
            "SZ_QYSDS_JDSBB_MXB", "SZ_GXQY_RJJCDL_YGMXB", "SZ_GXQY_RJJCDL_JBXX"
        ]
        for table in table_list:
            sql = f"DELETE FROM {table} WHERE NSRSBH = '{nsrsbh}'"
            logger.info(f'Executing: {sql}')
            cursor.execute(sql)
        return True
    except Exception as e:
        logger.error(f'Error deleting income tax data: {e}')
        return False


def make_income_tax_data(nsrsbh, cursor):
    """插入所得税数据"""
    try:
        batch_id = nsrsbh
        logger.info(f'Inserting batch ID: {batch_id}')

        SZ_QYSDS_JCXX_LIST_SQL = f"""
        INSERT INTO SZ_QYSDS_JCXX
        SELECT '{nsrsbh}', TICKET, SSSQQ, SSSQZ, XM, KMZ, LRSJ, ID, '{batch_id}', PCH
        FROM DATAGRID.SZ_QYSDS_JCXX
        WHERE NSRSBH = '9113070078982791X7'
        """
        SZ_QYSDS_JDSBB_LIST_SQL = f"""
        INSERT INTO SZ_QYSDS_JDSBB
        SELECT GXJSQY, KJXZXQY, GXJSQY_VALUE, KJXZXQY_VALUE, XXWLQY_VALUE, XXWLQY, BNLJ, HC, XM, LRSJ, SSSQQ, SSSQZ, ID, '{nsrsbh}', TICKET, '{batch_id}', PCH
        FROM DATAGRID.SZ_QYSDS_JDSBB
        WHERE NSRSBH = '91350211MA8UWMWH6J'
        """
        SZ_QYSDS_NDSBB_LIST_SQL = f"""
        INSERT INTO SZ_QYSDS_NDSBB
        SELECT HC, JS, LB, XM, LRSJ, SSSQQ, SSSQZ, ID, '{nsrsbh}', TICKET, '{batch_id}', PCH
        FROM DATAGRID.SZ_QYSDS_NDSBB
        WHERE NSRSBH = '9113070078982791X7'
        """
        SZ_QYSDS_GZXJ_LIST_SQL = f"""
        INSERT INTO SZ_QYSDS_GZXJ
        SELECT ZJJESZ, SSJESZ, SSGDKCLJG, SJFSESZ, QNLJJZKCESZ, NSTZJESZ, LJJZYHNDKCESE, HC1, GZXJZC, LRSJ, SSSQQ, SSSQZ, ID, '{nsrsbh}', TICKET, '{batch_id}', PCH
        FROM DATAGRID.SZ_QYSDS_GZXJ
        WHERE NSRSBH = '9113070078982791X7'
        """
        SZ_QYSDS_QJFYMXB_LIST_SQL = f"""
        INSERT INTO SZ_QYSDS_QJFYMXB
        SELECT CWFY, GLFY, HC, JWZF1, JWZF2, JWZF3, XM, XSFY, LRSJ, SSSQQ, SSSQZ, ID, '{nsrsbh}', TICKET, '{batch_id}', PCH
        FROM DATAGRID.SZ_QYSDS_QJFYMXB
        WHERE NSRSBH = '9113070078982791X7'
        """
        SZ_QYSDS_ZCZJ_LIST_SQL = f"""
        INSERT INTO SZ_QYSDS_ZCZJ
        SELECT ASSYBGDJSZJTXE, BNZJTXE, HC, JSZJTXTJE, LJZJTXE1, LJZJTXE2, NSTZJE, SSZKTXE, XM, ZCJSJC, ZCYZ, LRSJ, SSSQQ, SSSQZ, ID, '{nsrsbh}', TICKET, '{batch_id}', PCH
        FROM DATAGRID.SZ_QYSDS_ZCZJ
        WHERE NSRSBH = '91330206MA2AG7KL5W_jcdl4'
        """
        SZ_YAFY_YHMXB_LIST_SQL = f"""
        INSERT INTO SZ_YAFY_YHMXB
        SELECT '{nsrsbh}', HC, XM, JE, LRSJ, START_TIME, END_TIME, TICKET, PCH, '{batch_id}'
        FROM DATAGRID.SZ_YAFY_YHMXB
        WHERE NSRSBH = '9113070078982791X7'
        """
        SZ_GXQY_YHMXB_LIST_SQL = f"""
        INSERT INTO SZ_GXQY_YHMXB
        SELECT '{nsrsbh}', HC, XM, JE, LRSJ, START_TIME, END_TIME, TICKET, PCH, '{batch_id}'
        FROM DATAGRID.SZ_GXQY_YHMXB
        WHERE NSRSBH = '9113070078982791X7'
        """
        ZX_QYSDS_SRMXB_SQL = f"""
        INSERT INTO ZX_QYSDS_SRMXB
        SELECT '{nsrsbh}', SSSQQ, SSSQZ, XM, HC, JE, LRSJ, TICKET, '{batch_id}', PCH
        FROM DATAGRID.ZX_QYSDS_SRMXB
        WHERE NSRSBH = '91500107321778892T'
        """
        ZX_WAQZFSZ_SRNSTZMXB_SQL = f"""
        INSERT INTO ZX_WAQZFSZ_SRNSTZMXB
        SELECT '{nsrsbh}', SSSQQ, SSSQZ, HC, XM, HTJE, ZZJE_BN, ZZJE_LJ, SSJE_BN, SSJE_LJ, NSTZJE, PCH, LRSJ, TICKET, '{batch_id}'
        FROM DATAGRID.ZX_WAQZFSZ_SRNSTZMXB
        WHERE NSRSBH = '914603003230573_NEW'
        """
        ZX_ZCSSSQKC_NSTZMXB_SQL = f"""
        INSERT INTO ZX_ZCSSSQKC_NSTZMXB
        SELECT '{nsrsbh}', SSSQQ, SSSQZ, HC, XM, ZCSS_ZZJE, ZCSS_SYJE, ZCSS_HXJE, ZCCZ, PCSR, ZCJS, ZCSS_SSJE, NSTZJE, PCH, LRSJ, TICKET, '{batch_id}'
        FROM DATAGRID.ZX_ZCSSSQKC_NSTZMXB
        WHERE NSRSBH = '91440400572383350Q'
        """
        SZ_GXQY_YHMXB_ZDZCLY_SQL = f"""
        INSERT INTO SZ_GXQY_YHMXB_ZDZCLY
        SELECT '{nsrsbh}', SSSQQ, SSSQZ, YJLY, EJLY, SJLY, PCH, LRSJ, TICKET, '{batch_id}'
        FROM DATAGRID.SZ_GXQY_YHMXB_ZDZCLY
        WHERE NSRSBH = '91320281745566607R'
        """
        ZX_ZXYTCZXZJ_NSTZMXB_SQL = f"""
        INSERT INTO ZX_ZXYTCZXZJ_NSTZMXB
        SELECT '{nsrsbh}', SSSQQ, SSSQZ, HC, XM, QDND, CZXZJ, JE, QZJRBNSYDJE, QWND, QSND, QSAND, QEND, QYND, ZCJE, QZFYHZCJE, JYJE, QZSJCZJE, YJRBNYSSRJE, PCH, LRSJ, TICKET, '{batch_id}'
        FROM DATAGRID.ZX_ZXYTCZXZJ_NSTZMXB
        WHERE NSRSBH = '914603003230573_NEW'
        """
        SZ_QYSDS_JDSBB_MXB_SQL = f"""
        INSERT INTO SZ_QYSDS_JDSBB_MXB
        SELECT BNLJ, HC, XM, LRSJ, SSSQQ, SSSQZ, ID, '{nsrsbh}', TICKET, '{batch_id}', PCH
        FROM DATAGRID.SZ_QYSDS_JDSBB_MXB
        WHERE NSRSBH = '91320106MA1P4XDN4X'
        """
        SZ_GXQY_RJJCDL_YGMXB_SQL = f"""
        INSERT INTO SZ_GXQY_RJJCDL_YGMXB
        SELECT ID, '{nsrsbh}', SSSQQ, SSSQZ, SBRQ, HC, XM, JE, PCH, LRSJ, TICKET, '{batch_id}'
        FROM DATAGRID.SZ_GXQY_RJJCDL_YGMXB
        WHERE NSRSBH = '91220882MA0Y6_jcdl3'
        """
        SZ_GXQY_RJJCDL_JBXX_SQL = f"""
        INSERT INTO SZ_GXQY_RJJCDL_JBXX
        SELECT '{nsrsbh}', SSSQQ, SSSQZ, SBRQ, YHZZ, JMFS1, JMFS2, YHND1, YHND2, PCH, LRSJ, TICKET, '{batch_id}'
        FROM DATAGRID.SZ_GXQY_RJJCDL_JBXX
        WHERE NSRSBH = '91220882MA0Y6_jcdl3'
        """
        sql_list = [
            SZ_QYSDS_JCXX_LIST_SQL, SZ_QYSDS_JDSBB_LIST_SQL, SZ_QYSDS_NDSBB_LIST_SQL,
            SZ_QYSDS_GZXJ_LIST_SQL, SZ_QYSDS_QJFYMXB_LIST_SQL, SZ_QYSDS_ZCZJ_LIST_SQL,
            SZ_YAFY_YHMXB_LIST_SQL, SZ_GXQY_YHMXB_LIST_SQL, ZX_QYSDS_SRMXB_SQL,
            ZX_WAQZFSZ_SRNSTZMXB_SQL, ZX_ZCSSSQKC_NSTZMXB_SQL, SZ_GXQY_YHMXB_ZDZCLY_SQL,
            ZX_ZXYTCZXZJ_NSTZMXB_SQL, SZ_GXQY_RJJCDL_JBXX_SQL, SZ_GXQY_RJJCDL_YGMXB_SQL
        ]
        batch_sql = f"INSERT INTO T_SJZLJC_RZ_LEVEL@to_jrwz2_zx (BANKID, NSRSBH, NSRMC, LEVEL_DJ, LRSJ, SOURCE, REMARK, SOURCE_CODE, BATCH_ID) VALUES ('WZX01', '{nsrsbh}', NULL, 'T', SYSDATE+10, '电子税务', NULL, '1', '{batch_id}')"
        cursor.execute(f"DELETE FROM T_SJZLJC_RZ_LEVEL@to_jrwz2_zx WHERE NSRSBH = '{nsrsbh}'")
        cursor.execute(batch_sql)
        for sql in sql_list:
            logger.info(f'Executing income tax SQL: {sql}')
            cursor.execute(sql)
        return True
    except Exception as e:
        logger.error(f'Error making income tax data: {e}')
        return False


# ==================== 出口退税数据处理函数 ====================

def delete_export_tax_data(nsrsbh, cursor):
    """删除指定纳税人的出口退税数据"""
    try:
        table_list = ["CKTS_TMSBAB", "CKTS_TMSBAKZXX", "CKTS_TSSHJDCX", "CKTS_TSSHJDCXXQ",
                     "SCX_SBHZB", "SCX_SBMXB", "WMX_JHMXSBB", "WMX_CKMXSBB"]
        for table in table_list:
            sql = f"DELETE FROM {table} WHERE NSRSBH = '{nsrsbh}'"
            logger.info(f'Executing: {sql}')
            cursor.execute(sql)
        logger.info(f'Export tax data deleted for nsrsbh: {nsrsbh}')
        return True
    except Exception as e:
        logger.error(f'Error deleting export tax data: {e}')
        return False


def make_export_tax_data(nsrsbh, cursor):
    """插入出口退税数据"""
    try:
        batch_id = nsrsbh
        logger.info(f"插入的批次号： {batch_id}")

        CKTS_TMSBAB_SQL = f"""
        INSERT INTO CKTS_TMSBAB
        SELECT ID_TMSBA, LRSJ, TICKET, '{batch_id}', '{nsrsbh}', NSRMC, HGQYDM, TSSWJGDM,
               DWMYJYZBADJBBH, CKTSQYLXDM, TSKHYHMC, TSKHYHZH, CKTSZHBLTGDKYWBZ,
               QYBLTMSRYYXM, QYBLTMSRYYLXDH, QYBLTMSRYYSFZJHM, QYBLTMSRYEXM,
               QYBLTMSRYELXDH, QYBLTMSRYESFZJHM, CKHWTMSJSFFDM, TGLSLYSFWBZ,
               LSLYSFWDM, ZSQSDYBNSRBZ, XSZZSYHZC, CKTMSGLLX, FSZL
        FROM DATAGRID.CKTS_TMSBAB
        WHERE NSRSBH = '91320113MA1MLC9W5G'
        """
        CKTS_TMSBAKZXX_SQL = f"""
        INSERT INTO CKTS_TMSBAKZXX
        SELECT ID_BAKZ, LRSJ, '{nsrsbh}', NSRMC, TICKET, '{batch_id}', KZLXDM, KZLXMC,
               KZNR, YXBZ, YXQQ, YXQZ
        FROM DATAGRID.CKTS_TMSBAKZXX
        WHERE NSRSBH = '91320113MA1MLC9W5G'
        """
        CKTS_TSSHJDCX_SQL = f"""
        INSERT INTO CKTS_TSSHJDCX
        SELECT ID_TSSHJDCX, LRSJ, '{nsrsbh}', NSRMC, TICKET, '{batch_id}', LCHJMC,
               LCSWSXDM, SBRQ, ZLCLCSLID, DYSLTZSJ, CKQYGLLBDM, LCHJDM, SSQ, FFRQ,
               SBPC, FFBZ, WZHBZ, DJXH, STATE, TSMXBRN, LCSWSXMC, LCSLID
        FROM DATAGRID.CKTS_TSSHJDCX
        WHERE NSRSBH = '91320113MA1MLC9W5G'
        """
        CKTS_TSSHJDCXXQ_SQL = f"""
        INSERT INTO CKTS_TSSHJDCXXQ
        SELECT ID_TSSHJDCXXQ, LRSJ, '{nsrsbh}', NSRMC, TICKET, '{batch_id}', FSZZSTSE,
               ZKZZSTSE, TSRYDM, FSBYBLZZSTSE, QRBZ, SEHZXFSTSE, LCHJDM, FSBYBLTMSE,
               FSXFSTSE, SEHZMDSE, CLYJ, DJXH, JSSJ, STATE, SLXFSTSE, SEHZZZSTSE,
               LCSLID, LCHJMC, SLMDSE, TSSJ, FSMDSE, SLZZSTSE, FSBYBLXFSTSE, TYBZ,
               LCSLIDS, ZKXFSTSE, ZLCGS, JSRDM
        FROM DATAGRID.CKTS_TSSHJDCXXQ
        WHERE NSRSBH = '91320113MA1MLC9W5G'
        """
        SCX_SBHZB_SQL = f"""
        INSERT INTO SCX_SBHZB
        SELECT ID_SBHZB, LRSJ, '{nsrsbh}', NSRMC, TICKET, '{batch_id}', JLJGHXYTZBDMZHDKSE,
               BNLJYSFWBDMZHDKSE, JLJGHXYTZMDTSE, BNLJMDSE, MDTSBDMZHDKSE,
               BNLJCKHWBDMZHDKSE, YTZBDMZHDKSEYZZSNSSBBCE, BNLJJLJGHXYTZBDMZHDKSE,
               BNLJYTSE, BNLJCKHWMDTSE, SSQ, BNLJMDTCKXSERMB, MDTSEHJ, DJXH, MDSE,
               BNLJYSFWXSEMY, MDTSE, BNLJMDTSE, CKHWXSEMY, YSFWBDMZHDKSE, CKHWMDTSE,
               CKHWBDMZHDKSE, BNLJYSFWMDTSE, BNLJMDTCKXSEMY, ZZSNSSBBQMLDSE,
               MDTSBDMZHDKSEHJ, SQJZMDTSE, JZXQMDTSE, BNLJCKHWXSEMY, BDMZDKSEYNSBCE,
               YSFWXSEMY, BNLJJLJGHXYTZMDTSE, YTSE, JZBMZDKDJE, BNLJMDTSBDMZHDKSE,
               BNLJMDTSBDMZHDKSEHJ, CKXSERMB, BNLJMDTSEHJ, CKXSEMY, YSFWMDTSE
        FROM DATAGRID.SCX_SBHZB
        WHERE NSRSBH = '91320118MA225F318T'
        """
        SCX_SBMXB_SQL = f"""
        INSERT INTO SCX_SBMXB
        SELECT ID_SBMXB, LRSJ, '{nsrsbh}', NSRMC, TICKET, '{batch_id}', SSQ, SBXH, CKFPH,
               CKBGDH, CKRQ, DLZMHM, SPDM, SPMC, JLDWMC, CKSL, RMBLAJ, MYLAJ, ZSSL,
               TSL, JHFPL, BSLJJSJG, MSYCLJG, BMDKSE, MDTSE, JJDJCE, CKHTH, YWLX, BZ,
               SBSPDM, CJHBZMDM, CJZJ, CJHBHL, MYHL, CKTMSYWLXMCJH, MDTSNY, BYTSBZ,
               BYBLBZ, BYTSNY, ZBBLBZ, JSFPL
        FROM DATAGRID.SCX_SBMXB
        WHERE NSRSBH = '91130210684702045Q1'
        """
        WMX_JHMXSBB_SQL = f"""
        INSERT INTO WMX_JHMXSBB
        SELECT ID_JHMX, LRSJ, GHFNSRSBH, NSRMC, TICKET, '{batch_id}', SSQ, SBPC, SBXH,
               GLH, SZ, JHPZH, KPRQ, CKSPDM, SBHGSPMC, HGJLDWMC, SL, JSJE, ZSSL, TSL,
               TSE, BZ, ZYSPH, CKTMSYWLXMCJH, CKTMSYWLXDMJH, CKTMSPZLXDM, BYTSBZ,
               BYBLBZ, BYTSNY, ZBBLBZ, '{nsrsbh}'
        FROM DATAGRID.WMX_JHMXSBB
        WHERE NSRSBH = '91320411MA1MKT4P75'
        """
        WMX_CKMXSBB_SQL = f"""
        INSERT INTO WMX_CKMXSBB
        SELECT ID_CKMXSBB, LRSJ, '{nsrsbh}', NSRMC, TICKET, '{batch_id}', SSQ, SBPC, SBXH,
               GLH, CKFPH, TSE, CKBGDH, DLZMH, CKRQ, CKSPDM, CKSPMC, JLDWM, CKSL,
               MYLAJ, SBSPDM, SBSPMC, CKTMSYWLXDMJH, CKTMSYWLXMCJH, BZ, BYTSBZ,
               BYBLBZ, ZBBLBZ
        FROM DATAGRID.WMX_CKMXSBB
        WHERE NSRSBH = '91320411MA1MKT4P75'
        """
        batch_sql = f"""
        INSERT INTO T_SJZLJC_RZ_LEVEL@to_jrwz2_zx
        (BANKID, NSRSBH, NSRMC, LEVEL_DJ, LRSJ, SOURCE, REMARK, SOURCE_CODE, BATCH_ID)
        VALUES ('WZX01', '{nsrsbh}', NULL, 'T', SYSDATE, '电子税务', NULL, '1', '{batch_id}')
        """
        cursor.execute(f"DELETE FROM T_SJZLJC_RZ_LEVEL@to_jrwz2_zx WHERE NSRSBH = '{nsrsbh}'")
        cursor.execute(batch_sql)
        sql_list = [
            CKTS_TMSBAB_SQL, CKTS_TMSBAKZXX_SQL, CKTS_TSSHJDCX_SQL, CKTS_TSSHJDCXXQ_SQL,
            SCX_SBHZB_SQL, SCX_SBMXB_SQL, WMX_JHMXSBB_SQL, WMX_CKMXSBB_SQL
        ]
        for sql in sql_list:
            logger.info(f"正在插入数据：{sql}")
            cursor.execute(sql)
        return True
    except Exception as e:
        logger.error(f'Error making export tax data: {e}')
        return False
