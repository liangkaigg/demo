"""
报表查询服务 — 查询 SYT_REPORT_MOD_CONFIG / SYT_SQL_MOD_CONFIG 表。
提供 /api/report/search 接口，通过 Blueprint 注册到主应用。
"""
import os
from flask import Blueprint, request, jsonify, session
from functools import wraps
import cx_Oracle

report_bp = Blueprint("report", __name__)

# ---- 数据库配置 (与 db_service.py 共用环境变量) ----
DB_CONFIG = {
    "user": os.environ.get("DB_USER", "datagrid"),
    "password": os.environ.get("DB_PASSWORD", "datagrid"),
    "dsn": cx_Oracle.makedsn(
        os.environ.get("DB_HOST", "192.168.84.39"),
        os.environ.get("DB_PORT", "1521"),
        service_name=os.environ.get("DB_SERVICE", "NINVOICE"),
    ),
}

SQL_SEARCH = """
SELECT
    s.SQL_CONTENT,
    r.REPORT_MOD_ID,
    r.REPORT_MOD_MC,
    r.PARENT_MOD_MC,
    r.CREATE_USER,
    r.CREATE_TIME
FROM
    SYT_REPORT_MOD_CONFIG r
LEFT JOIN
    SYT_SQL_MOD_CONFIG s
    ON (r.CHILD_MOD_ID IS NOT NULL AND s.MOD_ID = r.CHILD_MOD_ID)
    OR (r.CHILD_MOD_ID IS NULL AND s.MOD_ID = r.PARENT_MOD_ID)
WHERE r.REPORT_MOD_MC LIKE :keyword
ORDER BY r.CREATE_TIME DESC
"""


def login_required(f):
    """简易登录校验 — 与主应用 session 保持兼容。"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return jsonify({"error": "未登录"}), 401
        return f(*args, **kwargs)
    return decorated


@report_bp.route("/api/report/search", methods=["POST"])
@login_required
def report_search():
    keyword = (request.get_json(silent=True) or {}).get("keyword", "").strip()
    if not keyword:
        return jsonify({"error": "请输入搜索关键词"}), 400

    like_val = f"%{keyword}%"
    conn = None
    try:
        conn = cx_Oracle.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute(SQL_SEARCH, {"keyword": like_val})

        # 列名列表
        columns = [col[0].lower() for col in cur.description]
        rows = []
        for row in cur:
            row_dict = {}
            for i, col_name in enumerate(columns):
                val = row[i]
                # datetime → 字符串
                if isinstance(val, cx_Oracle.Object) or hasattr(val, "isoformat"):
                    val = val.isoformat()
                row_dict[col_name] = val
            rows.append(row_dict)

        cur.close()
        return jsonify({"success": True, "columns": columns, "rows": rows, "count": len(rows)})
    except cx_Oracle.Error as e:
        error_obj = e.args[0] if e.args else e
        return jsonify({"error": f"数据库查询失败: {error_obj}"}), 500
    except Exception as e:
        return jsonify({"error": f"查询异常: {str(e)}"}), 500
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
