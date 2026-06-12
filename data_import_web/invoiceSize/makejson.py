import json
import random
import cx_Oracle
from decimal import Decimal, getcontext
from datetime import date, timedelta, datetime

# 设置Decimal精度，避免浮点误差
getcontext().prec = 28

# 默认购买方信息
PURCHASER_NAME = "张家口时代橡胶制品股份有限公司"
PURCHASER_TAX_NO = "9113070078982791X7"

# 可选的销售方列表（可自行扩展）
SALES_LIST = [
    {"name": "深圳瑞全餐饮管理有限公司", "tax_no": "914403002795314653"},
    {"name": "滴滴出行科技有限公司", "tax_no": "911201163409833307"},
    {"name": "北京京东世纪信息技术有限公司", "tax_no": "911101085512345678"},
    {"name": "上海华联超市股份有限公司", "tax_no": "913100001322123456"},
]

# 商品模板
COMMODITY_TEMPLATES = [
    {
        "commodity_name": "*餐饮服务*餐饮服务",
        "tax_rate": 6,
        "tax_classify_code": "3070401000000000000",
        "hwjc": "餐饮服务",
        "hwjc_1": "销售服务",
        "hwjc_2": "生活服务",
        "hwjc_3": "生活服务",
        "hwjc_4": "餐饮服务",
        "hwhlmc": "餐饮服务",
        "unit": "次"
    },
    {
        "commodity_name": "*运输服务*客运服务费",
        "tax_rate": 3,
        "tax_classify_code": "3010101020102000000",
        "hwjc": "运输服务",
        "hwjc_1": "销售服务",
        "hwjc_2": "运输服务",
        "hwjc_3": "运输服务",
        "hwjc_4": "运输服务",
        "hwhlmc": "其他公路旅客运输服务",
        "unit": "次"
    },
    {
        "commodity_name": "*办公用品*笔记本",
        "tax_rate": 13,
        "tax_classify_code": "1090101000000000000",
        "hwjc": "办公用品",
        "hwjc_1": "货物",
        "hwjc_2": "办公用品",
        "hwjc_3": "纸制品",
        "hwjc_4": "笔记本",
        "hwhlmc": "笔记本",
        "unit": "本"
    },
    {
        "commodity_name": "*住宿服务*住宿费",
        "tax_rate": 6,
        "tax_classify_code": "3070301000000000000",
        "hwjc": "住宿服务",
        "hwjc_1": "销售服务",
        "hwjc_2": "生活服务",
        "hwjc_3": "住宿服务",
        "hwjc_4": "住宿服务",
        "hwhlmc": "住宿服务",
        "unit": "晚"
    }
]


def random_digits(length):
    """生成指定长度的数字字符串"""
    return ''.join(str(random.randint(0, 9)) for _ in range(length))


def random_date():
    """生成最近两年内的随机日期（格式：YYYY-MM-DD）"""
    today = date.today()
    days_ago = random.randint(0, 730)
    d = today - timedelta(days=days_ago)
    return d.strftime("%Y-%m-%d")


def parse_date(date_str):
    """解析日期字符串，返回 datetime 对象"""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%Y-%m-%d')
    except:
        try:
            return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        except:
            return None


def generate_fpspmx(invoice_number, purchaser_tax_no):
    """生成发票明细列表（FPSPMX），返回 (明细列表, 总金额, 总税额)"""
    num_items = random.randint(1, 3)
    items = []
    total_amount = Decimal('0')
    total_tax = Decimal('0')

    for row in range(1, num_items + 1):
        template = random.choice(COMMODITY_TEMPLATES)
        quantity = Decimal(random.randint(1, 10))
        price = Decimal(random.randint(1000, 200000)) / 100
        amount = quantity * price
        tax_rate = Decimal(template['tax_rate'])
        tax = amount * tax_rate / 100

        amount = amount.quantize(Decimal('0.01'))
        tax = tax.quantize(Decimal('0.01'))

        total_amount += amount
        total_tax += tax

        item = {
            "AMOUNT": str(amount),
            "QUANTITY": str(quantity),
            "TAX": str(tax),
            "HWJC_3": template['hwjc_3'],
            "HWJC_4": template['hwjc_4'],
            "HWJC_1": template['hwjc_1'],
            "UNIT_PRICE": str(price),
            "HWJC_2": template['hwjc_2'],
            "TAX_RATE": str(template['tax_rate']),
            "INVOICE_CODE": "全电发票",
            "UNIT": template['unit'],
            "NSRSBH": purchaser_tax_no,
            "TAX_CLASSIFY_CODE": template['tax_classify_code'],
            "SPECIFICATION_MODEL": "",
            "HWJC": template['hwjc'],
            "ROW_NO": str(row),
            "INVOICE_NUMBER": invoice_number,
            "COMMODITY_NAME": template['commodity_name'],
            "HWHLWMC": template['hwhlmc']
        }
        items.append(item)

    total_amount = total_amount.quantize(Decimal('0.01'))
    total_tax = total_tax.quantize(Decimal('0.01'))
    return items, total_amount, total_tax


def generate_fpxx(invoice_number, id_str, billing_date, sales,
                  purchaser_name, purchaser_tax_no, create_time):
    """生成完整的 FPXX 对象"""
    fpspmx, total_amount, total_tax = generate_fpspmx(invoice_number, purchaser_tax_no)
    amount_tax = total_amount + total_tax

    return {
        "AMOUNT_TAX": str(amount_tax),
        "BILLING_DATE": billing_date,
        "CHECK_CODE": "",
        "CREATE_TIME": create_time,
        "DATA_TYPE": "1",
        "ID": id_str,
        "INVOICE_CODE": "全电发票",
        "INVOICE_NUMBER": invoice_number,
        "INVOICE_TYPE": "10",
        "NSRMC": purchaser_name,
        "NSRSBH": purchaser_tax_no,
        "PURCHASER_ADDRESS_PHONE": "",
        "PURCHASER_BANK": "",
        "PURCHASER_NAME": purchaser_name,
        "PURCHASER_TAX_NO": purchaser_tax_no,
        "SALES_ADDRESS_PHONE": "",
        "SALES_BANK": "",
        "SALES_NAME": sales['name'],
        "SALES_TAX_NO": sales['tax_no'],
        "STATE": "0",
        "TOTAL_AMOUNT": str(total_amount),
        "TOTAL_TAX": str(total_tax),
        "UPDATE_TIME": "",
        "IS_CERT": "",
        "DEDUCTIBLE_TYPE": "",
        "DEDUCTIBLE_MODE": "",
        "FPSPMX": fpspmx
    }


def generate_json(output_file, purchaser_name, purchaser_tax_no, target_size_bytes):
    """生成发票JSON文件，返回生成的记录数和文件路径"""
    create_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write('[')
        f.flush()
        first = True
        count = 0

        while True:
            invoice_number = random_digits(20)
            id_str = random_digits(19)
            billing_date = random_date()
            sales = random.choice(SALES_LIST)

            fpxx = generate_fpxx(
                invoice_number, id_str, billing_date, sales,
                purchaser_name, purchaser_tax_no, create_time
            )

            record = json.dumps({"FPXX": fpxx}, separators=(',', ':'), ensure_ascii=False)

            current_pos = f.tell()
            next_record_size = len(record)
            if not first:
                next_record_size += 1
            total_if_add = current_pos + next_record_size + 2  # ']}' 结尾

            if total_if_add > target_size_bytes:
                print(f"达到目标大小，当前: {current_pos} 字节，停止于第 {count} 条记录")
                break

            if not first:
                f.write(',')
            f.write(record)
            f.flush()
            first = False
            count += 1

            if count % 1000 == 0:
                print(f"  已写入 {count} 条记录，当前文件: {f.tell()} 字节")

        f.write(']')
        f.flush()
        final_size = f.tell()
        print(f"生成完成！共 {count} 条记录，文件大小: {final_size} 字节 ({final_size/1024/1024:.2f} MB)")
        return count, final_size


def import_invoice_data(json_file):
    """导入发票主表和商品明细数据到数据库"""
    print(f"\n正在读取文件: {json_file}")
    with open(json_file, 'r', encoding='utf-8') as f:
        json_data = json.load(f)

    # 适配格式: [{"FPXX": {...}}, ...] 或 {"kydInvoiceArray": [...]}
    if isinstance(json_data, dict) and 'kydInvoiceArray' in json_data:
        data = json_data['kydInvoiceArray']
        print(f"检测到 kydInvoiceArray 格式")
    elif isinstance(json_data, list):
        data = json_data
        print(f"检测到数组格式")
    else:
        raise ValueError("不支持的JSON格式")

    print(f"共 {len(data)} 条发票记录")

    print("正在连接数据库...")
    connection = cx_Oracle.connect(
        user="datagrid",
        password="datagrid",
        dsn="192.168.85.64:1521/emserver",
        encoding="UTF-8"
    )
    cursor = connection.cursor()

    # 提取税号并执行删除
    tax_no = None
    if data and data[0].get('FPXX', {}).get('PURCHASER_TAX_NO'):
        tax_no = data[0]['FPXX']['PURCHASER_TAX_NO']
    elif data and data[0].get('FPXX', {}).get('NSRSBH'):
        tax_no = data[0]['FPXX']['NSRSBH']

    if tax_no:
        print(f"正在清理税号 {tax_no} 的旧数据...")
        cursor.execute("DELETE FROM INVOICE_GENERAL_0238 WHERE CLIENT_NSRSBH = :tax_no", {"tax_no": tax_no})
        cursor.execute("DELETE FROM INVOICE_ITEM_0238 WHERE DATA_NSRSBH = :tax_no", {"tax_no": tax_no})
        connection.commit()
        print("旧数据已清理")

    insert_fpxx_sql = """
    INSERT INTO INVOICE_GENERAL_0238 (
        INVOICE_CODE, INVOICE_NUMBER, BILLING_DATE, INVOICE_TYPE,
        DATA_TYPE, CHECK_CODE, INVOICE_STATE, AMOUNT_TAX,
        PURCHASER, PURCHASE_TAX_CODE, PURCHASE_BANK, PURCHASE_ADDRESS,
        PURCHASE_MOBILE, SALER, SALE_TAX_CODE, SALE_BANK,
        SALE_ADDRESS, SALE_MOBILE, TOTAL_AMOUNT, TOTAL_TAX,
        REMARK, DRAWER, REVIEWER, PAYEE,
        TAX_RATE, TAX, DEDUCTIBLE, DEDUCTIBLE_TYPE,
        DEDUCTIBLE_MODE, CLIENT_NSRSBH, CREATE_TIME, YEARMONTH,
        UPDATE_TIME, ID, BILLING_DATETIME
    ) VALUES (
        :1, :2, :3, :4, :5, :6, :7, :8, :9, :10,
        :11, :12, :13, :14, :15, :16, :17, :18, :19, :20,
        :21, :22, :23, :24, :25, :26, :27, :28, :29, :30,
        :31, :32, :33, :34, :35
    )
    """

    insert_item_sql = """
    INSERT INTO INVOICE_ITEM_0238 (
        ID, ROW_NO, UNIT_PRICE, AMOUNT, TAX_RATE, QUANTITY,
        TAX_CLASSIFY_CODE, COMMODITY_NAME, SPECIFICATION_MODEL, UNIT,
        TAX, INVOICE_NUMBER, INVOICE_CODE, INVOICE_TYPE,
        BILLING_DATE, DATA_TYPE, STATE, PURCHASER_NAME,
        SALES_NAME, SALES_TAX_NO, DATA_NSRSBH, CREATE_TIME,
        PURCHASER_TAX_NO, BILLING_DATETIME
    ) VALUES (
        :1, :2, :3, :4, :5, :6, :7, :8, :9, :10,
        :11, :12, :13, :14, :15, :16, :17, :18,
        :19, :20, :21, :22, :23, :24
    )
    """

    fpxx_success = 0
    fpxx_error = 0
    item_success = 0
    item_error = 0
    total_items = 0

    for idx, record in enumerate(data, 1):
        fpxx = record.get('FPXX', {})
        fpspmx_list = fpxx.get('FPSPMX', [])

        invoice_code = fpxx.get('INVOICE_CODE', '')
        invoice_number = fpxx.get('INVOICE_NUMBER', '')

        # 1. 插入发票主表
        try:
            billing_date = parse_date(fpxx.get('BILLING_DATE'))
            create_time = parse_date(fpxx.get('CREATE_TIME'))
            update_time = parse_date(fpxx.get('UPDATE_TIME'))

            yearmonth = None
            if billing_date:
                yearmonth = billing_date.strftime('%Y%m')

            fpxx_values = (
                invoice_code,                           # INVOICE_CODE
                invoice_number,                         # INVOICE_NUMBER
                billing_date,                           # BILLING_DATE
                fpxx.get('INVOICE_TYPE'),              # INVOICE_TYPE
                fpxx.get('DATA_TYPE'),                 # DATA_TYPE
                fpxx.get('CHECK_CODE'),                # CHECK_CODE
                fpxx.get('STATE'),                     # INVOICE_STATE
                fpxx.get('AMOUNT_TAX'),                # AMOUNT_TAX
                fpxx.get('PURCHASER_NAME'),            # PURCHASER
                fpxx.get('PURCHASER_TAX_NO'),          # PURCHASE_TAX_CODE
                fpxx.get('PURCHASER_BANK'),            # PURCHASE_BANK
                fpxx.get('PURCHASER_ADDRESS_PHONE'),   # PURCHASE_ADDRESS
                None,                                   # PURCHASE_MOBILE
                fpxx.get('SALES_NAME'),                # SALER
                fpxx.get('SALES_TAX_NO'),              # SALE_TAX_CODE
                fpxx.get('SALES_BANK'),                # SALE_BANK
                fpxx.get('SALES_ADDRESS_PHONE'),       # SALE_ADDRESS
                None,                                   # SALE_MOBILE
                fpxx.get('TOTAL_AMOUNT'),              # TOTAL_AMOUNT
                fpxx.get('TOTAL_TAX'),                 # TOTAL_TAX
                None,                                   # REMARK
                None,                                   # DRAWER
                None,                                   # REVIEWER
                None,                                   # PAYEE
                None,                                   # TAX_RATE
                None,                                   # TAX
                fpxx.get('DEDUCTIBLE'),                # DEDUCTIBLE
                fpxx.get('DEDUCTIBLE_TYPE'),           # DEDUCTIBLE_TYPE
                fpxx.get('DEDUCTIBLE_MODE'),           # DEDUCTIBLE_MODE
                fpxx.get('NSRSBH'),                    # CLIENT_NSRSBH
                create_time,                            # CREATE_TIME
                yearmonth,                              # YEARMONTH
                update_time,                            # UPDATE_TIME
                fpxx.get('ID'),                        # ID
                billing_date                            # BILLING_DATETIME
            )

            cursor.execute(insert_fpxx_sql, fpxx_values)
            fpxx_success += 1

        except Exception as e:
            fpxx_error += 1
            if fpxx_error <= 5:
                print(f"  ✗ 主表记录 {idx} 失败: {str(e)[:100]}")
            continue

        # 2. 插入商品明细表
        if not fpspmx_list:
            continue

        for item in fpspmx_list:
            total_items += 1

            try:
                item_id = total_items

                item_values = (
                    item_id,                                    # ID
                    item.get('ROW_NO'),                        # ROW_NO
                    item.get('UNIT_PRICE'),                    # UNIT_PRICE
                    item.get('AMOUNT'),                        # AMOUNT
                    item.get('TAX_RATE'),                      # TAX_RATE
                    item.get('QUANTITY'),                      # QUANTITY
                    item.get('TAX_CLASSIFY_CODE'),             # TAX_CLASSIFY_CODE
                    item.get('COMMODITY_NAME'),                # COMMODITY_NAME
                    item.get('SPECIFICATION_MODEL'),           # SPECIFICATION_MODEL
                    item.get('UNIT'),                          # UNIT
                    item.get('TAX'),                           # TAX
                    item.get('INVOICE_NUMBER'),                # INVOICE_NUMBER
                    item.get('INVOICE_CODE'),                  # INVOICE_CODE
                    fpxx.get('INVOICE_TYPE'),                  # INVOICE_TYPE
                    billing_date,                              # BILLING_DATE
                    fpxx.get('DATA_TYPE'),                     # DATA_TYPE
                    fpxx.get('STATE'),                         # STATE
                    fpxx.get('PURCHASER_NAME'),                # PURCHASER_NAME
                    fpxx.get('SALES_NAME'),                    # SALES_NAME
                    fpxx.get('SALES_TAX_NO'),                  # SALES_TAX_NO
                    item.get('NSRSBH'),                        # DATA_NSRSBH
                    create_time,                               # CREATE_TIME
                    fpxx.get('PURCHASER_TAX_NO'),              # PURCHASER_TAX_NO
                    billing_date                               # BILLING_DATETIME
                )

                cursor.execute(insert_item_sql, item_values)
                item_success += 1

            except Exception as e:
                item_error += 1
                if item_error <= 5:
                    print(f"  ✗ 明细 ROW_NO={item.get('ROW_NO')} 失败: {str(e)[:100]}")

        if idx % 5000 == 0:
            connection.commit()
            print(f"  已导入 {idx}/{len(data)} 条，主表成功: {fpxx_success}，明细成功: {item_success}")

    connection.commit()
    cursor.close()
    connection.close()

    print(f"\n导入完成！")
    print(f"  主表: 成功 {fpxx_success}, 失败 {fpxx_error}")
    print(f"  明细: 成功 {item_success}, 失败 {item_error}")


def generate_and_import(name, tax_no, target_size_bytes):
    """直接生成发票数据并流式入库，跳过文件读写"""
    create_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("正在连接数据库...")
    connection = cx_Oracle.connect(
        user="datagrid",
        password="datagrid",
        dsn="192.168.85.64:1521/emserver",
        encoding="UTF-8"
    )
    cursor = connection.cursor()

    # 先删除旧数据
    print(f"正在清理税号 {tax_no} 的旧数据...")
    cursor.execute("DELETE FROM INVOICE_GENERAL_0238 WHERE CLIENT_NSRSBH = :tax_no", {"tax_no": tax_no})
    cursor.execute("DELETE FROM INVOICE_ITEM_0238 WHERE DATA_NSRSBH = :tax_no", {"tax_no": tax_no})
    connection.commit()
    print("旧数据已清理")

    insert_fpxx_sql = """
    INSERT INTO INVOICE_GENERAL_0238 (
        INVOICE_CODE, INVOICE_NUMBER, BILLING_DATE, INVOICE_TYPE,
        DATA_TYPE, CHECK_CODE, INVOICE_STATE, AMOUNT_TAX,
        PURCHASER, PURCHASE_TAX_CODE, PURCHASE_BANK, PURCHASE_ADDRESS,
        PURCHASE_MOBILE, SALER, SALE_TAX_CODE, SALE_BANK,
        SALE_ADDRESS, SALE_MOBILE, TOTAL_AMOUNT, TOTAL_TAX,
        REMARK, DRAWER, REVIEWER, PAYEE,
        TAX_RATE, TAX, DEDUCTIBLE, DEDUCTIBLE_TYPE,
        DEDUCTIBLE_MODE, CLIENT_NSRSBH, CREATE_TIME, YEARMONTH,
        UPDATE_TIME, ID, BILLING_DATETIME
    ) VALUES (
        :1, :2, :3, :4, :5, :6, :7, :8, :9, :10,
        :11, :12, :13, :14, :15, :16, :17, :18, :19, :20,
        :21, :22, :23, :24, :25, :26, :27, :28, :29, :30,
        :31, :32, :33, :34, :35
    )
    """

    insert_item_sql = """
    INSERT INTO INVOICE_ITEM_0238 (
        ID, ROW_NO, UNIT_PRICE, AMOUNT, TAX_RATE, QUANTITY,
        TAX_CLASSIFY_CODE, COMMODITY_NAME, SPECIFICATION_MODEL, UNIT,
        TAX, INVOICE_NUMBER, INVOICE_CODE, INVOICE_TYPE,
        BILLING_DATE, DATA_TYPE, STATE, PURCHASER_NAME,
        SALES_NAME, SALES_TAX_NO, DATA_NSRSBH, CREATE_TIME,
        PURCHASER_TAX_NO, BILLING_DATETIME
    ) VALUES (
        :1, :2, :3, :4, :5, :6, :7, :8, :9, :10,
        :11, :12, :13, :14, :15, :16, :17, :18,
        :19, :20, :21, :22, :23, :24
    )
    """

    fpxx_success = 0
    fpxx_error = 0
    item_success = 0
    item_error = 0
    total_items = 0
    count = 0
    # 模拟 JSON 文件大小：'[' + records + ',' + ']'
    simulated_size = 1  # '['

    while True:
        invoice_number = random_digits(20)
        id_str = random_digits(19)
        billing_date = random_date()
        sales = random.choice(SALES_LIST)

        fpxx = generate_fpxx(
            invoice_number, id_str, billing_date, sales,
            name, tax_no, create_time
        )

        # 模拟 JSON 记录大小来估算文件大小
        record = json.dumps({"FPXX": fpxx}, separators=(',', ':'), ensure_ascii=False)
        next_size = len(record)
        if count > 0:
            next_size += 1  # comma
        if simulated_size + next_size + 1 > target_size_bytes:  # +1 for ']'
            print(f"达到目标大小，停止于第 {count} 条记录")
            break

        simulated_size += next_size
        count += 1

        fpspmx_list = fpxx.get('FPSPMX', [])
        billing_date_dt = parse_date(billing_date)
        create_time_dt = parse_date(create_time)

        yearmonth = billing_date_dt.strftime('%Y%m') if billing_date_dt else None

        # 插入主表
        try:
            fpxx_values = (
                fpxx.get('INVOICE_CODE'),              # INVOICE_CODE
                invoice_number,                         # INVOICE_NUMBER
                billing_date_dt,                        # BILLING_DATE
                fpxx.get('INVOICE_TYPE'),              # INVOICE_TYPE
                fpxx.get('DATA_TYPE'),                 # DATA_TYPE
                fpxx.get('CHECK_CODE'),                # CHECK_CODE
                fpxx.get('STATE'),                     # INVOICE_STATE
                fpxx.get('AMOUNT_TAX'),                # AMOUNT_TAX
                name,                                   # PURCHASER
                tax_no,                                 # PURCHASE_TAX_CODE
                fpxx.get('PURCHASER_BANK'),            # PURCHASE_BANK
                fpxx.get('PURCHASER_ADDRESS_PHONE'),   # PURCHASE_ADDRESS
                None,                                   # PURCHASE_MOBILE
                sales['name'],                          # SALER
                sales['tax_no'],                        # SALE_TAX_CODE
                fpxx.get('SALES_BANK'),                # SALE_BANK
                fpxx.get('SALES_ADDRESS_PHONE'),       # SALE_ADDRESS
                None,                                   # SALE_MOBILE
                fpxx.get('TOTAL_AMOUNT'),              # TOTAL_AMOUNT
                fpxx.get('TOTAL_TAX'),                 # TOTAL_TAX
                None,                                   # REMARK
                None,                                   # DRAWER
                None,                                   # REVIEWER
                None,                                   # PAYEE
                None,                                   # TAX_RATE
                None,                                   # TAX
                fpxx.get('DEDUCTIBLE'),                # DEDUCTIBLE
                fpxx.get('DEDUCTIBLE_TYPE'),           # DEDUCTIBLE_TYPE
                fpxx.get('DEDUCTIBLE_MODE'),           # DEDUCTIBLE_MODE
                tax_no,                                 # CLIENT_NSRSBH
                create_time_dt,                         # CREATE_TIME
                yearmonth,                              # YEARMONTH
                None,                                   # UPDATE_TIME
                id_str,                                 # ID
                billing_date_dt                         # BILLING_DATETIME
            )
            cursor.execute(insert_fpxx_sql, fpxx_values)
            fpxx_success += 1
        except Exception as e:
            fpxx_error += 1
            if fpxx_error <= 5:
                print(f"  ✗ 主表记录 {count} 失败: {str(e)[:100]}")
            continue

        # 插入明细表
        for item in fpspmx_list:
            total_items += 1
            try:
                item_values = (
                    total_items,                            # ID
                    item.get('ROW_NO'),                    # ROW_NO
                    item.get('UNIT_PRICE'),                # UNIT_PRICE
                    item.get('AMOUNT'),                    # AMOUNT
                    item.get('TAX_RATE'),                  # TAX_RATE
                    item.get('QUANTITY'),                  # QUANTITY
                    item.get('TAX_CLASSIFY_CODE'),         # TAX_CLASSIFY_CODE
                    item.get('COMMODITY_NAME'),            # COMMODITY_NAME
                    item.get('SPECIFICATION_MODEL'),       # SPECIFICATION_MODEL
                    item.get('UNIT'),                      # UNIT
                    item.get('TAX'),                       # TAX
                    invoice_number,                        # INVOICE_NUMBER
                    fpxx.get('INVOICE_CODE'),              # INVOICE_CODE
                    fpxx.get('INVOICE_TYPE'),              # INVOICE_TYPE
                    billing_date_dt,                        # BILLING_DATE
                    fpxx.get('DATA_TYPE'),                 # DATA_TYPE
                    fpxx.get('STATE'),                     # STATE
                    name,                                   # PURCHASER_NAME
                    sales['name'],                          # SALES_NAME
                    sales['tax_no'],                        # SALES_TAX_NO
                    tax_no,                                 # DATA_NSRSBH
                    create_time_dt,                         # CREATE_TIME
                    tax_no,                                 # PURCHASER_TAX_NO
                    billing_date_dt                         # BILLING_DATETIME
                )
                cursor.execute(insert_item_sql, item_values)
                item_success += 1
            except Exception as e:
                item_error += 1
                if item_error <= 5:
                    print(f"  ✗ 明细 失败: {str(e)[:100]}")

        if count % 5000 == 0:
            connection.commit()
            print(f"  已生成并入库 {count} 条，主表: {fpxx_success}，明细: {item_success}")

    connection.commit()
    cursor.close()
    connection.close()

    print(f"\n流式入库完成！")
    print(f"  主表: 成功 {fpxx_success}, 失败 {fpxx_error}")
    print(f"  明细: 成功 {item_success}, 失败 {item_error}")
    return count, simulated_size


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="发票JSON数据生成与导入工具")
    parser.add_argument("--name", default=None, help=f"购买方名称（默认: {PURCHASER_NAME}）")
    parser.add_argument("--tax-no", default=None, help=f"购买方税号（默认: {PURCHASER_TAX_NO}）")
    parser.add_argument("--size-mb", type=float, default=10, help="目标文件大小（MB），默认10")
    parser.add_argument("--output", default="模版.json", help="输出JSON文件路径（默认: 模版.json）")
    parser.add_argument("--import", dest="do_import", action="store_true", help="生成后自动导入数据库")
    args = parser.parse_args()

    purchaser_name = args.name or PURCHASER_NAME
    purchaser_tax_no = args.tax_no or PURCHASER_TAX_NO
    target_size_bytes = int(args.size_mb * 1024 * 1024)

    print("=" * 60)
    print("发票JSON数据生成与导入工具")
    print("=" * 60)
    print(f"  购买方: {purchaser_name}")
    print(f"  税号:   {purchaser_tax_no}")
    print(f"  目标大小: {args.size_mb} MB")
    print(f"  输出文件: {args.output}")

    # Step 1: 生成JSON文件
    generate_json(args.output, purchaser_name, purchaser_tax_no, target_size_bytes)

    # Step 2: 导入数据库
    if args.do_import:
        print()
        import_invoice_data(args.output)
    else:
        print(f"\n未指定 --import，跳过数据库导入。使用 --import 启用自动导入。")
