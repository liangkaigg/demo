/* ============================================
   数据管理平台 - Interactions
   ============================================ */

// ---- Session check: redirect to login on 401 ----
async function apiFetch(url, options = {}) {
  const res = await fetch(APP_ROOT + url, options);
  if (res.status === 401) {
    window.location.href = APP_ROOT + '/login';
    throw new Error('未登录，请先登录');
  }
  return res;
}

// ---- Navigation Tab Switching ----
document.querySelectorAll('.nav-tab').forEach(btn => {
  btn.addEventListener('click', () => {
    const tabId = btn.dataset.tab;

    // Update nav tabs
    document.querySelectorAll('.nav-tab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    // Update panels with animation
    document.querySelectorAll('.tab-panel').forEach(panel => {
      panel.classList.remove('active');
      panel.style.opacity = '0';
      panel.style.transform = 'translateY(12px)';
    });

    const activePanel = document.getElementById('panel-' + tabId);
    activePanel.classList.add('active');
    // Force reflow for animation
    void activePanel.offsetWidth;
    activePanel.style.opacity = '1';
    activePanel.style.transform = 'translateY(0)';
  });
});

// ---- Show/hide VAT extra fields ----
document.getElementById('type_vat')?.addEventListener('change', (e) => {
  document.getElementById('vat_extra_fields').style.display = e.target.checked ? 'block' : 'none';
});

// ---- Helper: show result in result-card ----
function showResult(el, type, msg) {
  el.className = 'result-card ' + type + ' visible';
  el.textContent = msg;
}

// ---- Loading Overlay Helpers ----
function showLoadingOverlay(title, desc) {
  const overlay = document.getElementById('loadingOverlay');
  if (!overlay) return;
  overlay.querySelector('.loading-title').textContent = title || '数据导入中';
  overlay.querySelector('.loading-desc').textContent = desc || '正在处理，请耐心等待...';
  const barFill = overlay.querySelector('.loading-bar-fill');
  if (barFill) barFill.style.width = '0%';
  overlay.style.display = 'flex';
}
function hideLoadingOverlay() {
  const overlay = document.getElementById('loadingOverlay');
  if (overlay) overlay.style.display = 'none';
}

// ---- Data Single Form (combined invoice + tax) ----
document.getElementById('dataSingleForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const result = document.getElementById('dataResult');
  showResult(result, 'loading', '处理中...');

  const nsrsbh = document.getElementById('data_nsrsbh').value;
  const company = document.getElementById('data_company').value;
  const invoice = document.getElementById('type_invoice').checked;
  const vat = document.getElementById('type_vat').checked;
  const exportTax = document.getElementById('type_export').checked;
  const income = document.getElementById('type_income').checked;

  if (!invoice && !vat && !exportTax && !income) {
    showResult(result, 'error', '请至少选择一种数据类型');
    return;
  }

  // Show loading overlay
  showLoadingOverlay('数据处理中', '正在提交数据，请耐心等待...');

  let results = [];

  try {
    if (invoice) {
      const res = await apiFetch('/api/invoice/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nsrsbh, company })
      });
      const data = await res.json();
      results.push(`发票: ${data.success ? '✓ 成功' : '✗ ' + data.error}`);
    }

    if (vat) {
      const res = await apiFetch('/api/tax/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nsrsbh, company,
          name: document.getElementById('data_name').value || null,
          zjhm: document.getElementById('data_zjhm').value || null,
          num: 10000
        })
      });
      const data = await res.json();
      results.push(`增值税: ${data.success ? '✓ 成功' : '✗ ' + data.error}`);
    }

    if (exportTax) {
      const res = await apiFetch('/api/export/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nsrsbh })
      });
      const data = await res.json();
      results.push(`出口退税: ${data.success ? '✓ 成功' : '✗ ' + data.error}`);
    }

    if (income) {
      const res = await apiFetch('/api/incometax/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nsrsbh })
      });
      const data = await res.json();
      results.push(`所得税: ${data.success ? '✓ 成功' : '✗ ' + data.error}`);
    }

    const allSuccess = results.every(r => r.includes('✓'));
    showResult(result, allSuccess ? 'success' : 'error', results.join('\n'));
  } catch (err) {
    showResult(result, 'error', '请求失败: ' + err.message);
  } finally {
    hideLoadingOverlay();
  }
});

// ---- ZIP file selection ----
const fileDrop = document.getElementById('fileDrop');
const zipFileInput = document.getElementById('zip_file');
const zipFileName = document.getElementById('zipFileName');

if (fileDrop) {
  fileDrop.addEventListener('click', () => zipFileInput.click());

  fileDrop.addEventListener('dragover', (e) => {
    e.preventDefault();
    fileDrop.classList.add('dragover');
  });
  fileDrop.addEventListener('dragleave', () => {
    fileDrop.classList.remove('dragover');
  });
}

if (zipFileInput) {
  zipFileInput.addEventListener('change', () => {
    zipFileName.textContent = zipFileInput.files[0]?.name || '';
  });
}

// ---- ZIP Import ----
document.getElementById('zipImportForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const result = document.getElementById('importResult');
  const file = zipFileInput.files[0];

  if (!file) {
    showResult(result, 'error', '请先选择 ZIP 文件');
    return;
  }

  showLoadingOverlay('数据导入中', '正在处理和导入 SQL 文件，请耐心等待...');
  const barFill = document.querySelector('.loading-bar-fill');
  const progressEl = document.getElementById('loadingProgress');
  barFill.style.width = '10%';
  progressEl.textContent = '准备中...';

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await apiFetch('/api/import/zip', { method: 'POST', body: formData });
    const data = await res.json();

    barFill.style.width = '100%';
    progressEl.textContent = '处理完成';

    // Small delay so user sees 100%
    await new Promise(r => setTimeout(r, 400));

    if (data.success) {
      let msg = `处理完成\n\n`;
      msg += `SQL 文件数: ${data.total_files}\n\n`;
      msg += `发票数据:\n  ✓ 成功: ${data.invoice_success} 条\n  ⊘ 跳过: ${data.invoice_skip} 条\n\n`;
      msg += `税务数据:\n  ✓ 成功: ${data.tax_success} 条\n`;
      if (data.errors && data.errors.length > 0) {
        msg += `\n错误信息 (前20条):\n${data.errors.join('\n')}`;
      }
      showResult(result, 'success', msg);
    } else {
      showResult(result, 'error', data.error || '导入失败');
    }
  } catch (err) {
    showResult(result, 'error', '请求失败: ' + err.message);
  } finally {
    hideLoadingOverlay();
  }
});

// ---- Invoice Generation Form ----
document.getElementById('invoiceGenForm')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const result = document.getElementById('invoiceGenResult');

  const tax_no = document.getElementById('gen_tax_no').value.trim();
  const name = document.getElementById('gen_company').value.trim();
  const size_mb = parseFloat(document.getElementById('gen_size_mb').value);

  if (!tax_no || !name) {
    showResult(result, 'error', '请填写税号和企业名称');
    return;
  }
  if (!size_mb || size_mb <= 0) {
    showResult(result, 'error', '目标数据量必须大于0');
    return;
  }

  showLoadingOverlay('发票数据生成中', `正在生成 ${size_mb}MB 数据并导入数据库...`);
  showResult(result, 'loading', '正在生成数据并入库，请耐心等待...');

  try {
    const res = await apiFetch('/api/invoice/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, tax_no, size_mb })
    });
    const data = await res.json();

    if (data.success) {
      const msg = `生成并入库成功！\n\n税号: ${data.tax_no}\n企业: ${data.company}\n记录数: ${data.records} 条\n文件大小: ${data.file_size_mb} MB`;
      showResult(result, 'success', msg);
    } else {
      showResult(result, 'error', data.error || '生成失败');
    }
  } catch (err) {
    showResult(result, 'error', '请求失败: ' + err.message);
  } finally {
    hideLoadingOverlay();
  }
});

// ---- Delete Data Form ----
document.getElementById('deleteDataForm')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const result = document.getElementById('deleteResult');
  const nsrsbhText = document.getElementById('delete_nsrsbh').value.trim();

  if (!nsrsbhText) {
    showResult(result, 'error', '请输入纳税人识别号');
    return;
  }

  if (!confirm('确认删除这些税号的数据吗？此操作不可恢复！')) {
    return;
  }

  showResult(result, 'loading', '正在删除数据...');

  try {
    const res = await apiFetch('/api/import/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nsrsbh_list: nsrsbhText })
    });
    const data = await res.json();
    showResult(result, data.success ? 'success' : 'error', data.message || data.error);
  } catch (err) {
    showResult(result, 'error', '删除失败: ' + err.message);
  }
});

// ==========================================
// JSON Tool - State
// ==========================================
let jsonWorkbook = null;
let jsonData = null;
let sheetDataMap = new Map();
let uploadedFileName = '';
let fieldMapping = null;
let mappingStats = null;
let templateFileName = '';

// 税务数据元信息：sheet中文名 + 中英文表头映射
const TAX_SHEET_META = {
  NSRJCXX: {
    name: '1.企业基本信息(NSRJCXX)',
    en: ['DJZCLXDM','SYKJZDMC','JYFW','ZCD_DHHM','SYKJZD','NSRZTDM','ZCZBBZ','NSRZTMC','YB','ZGY','KYRQ','SSHYMC','DJZCLXMC','NSLXDM','ZCDZ','GSZCH','DS_DM','NSRSBH','HYMLDM','YYDZ','HYMLMC','LSGXDM','DS_MC','HZDJRQ','DBR_DHHM','NSLXMC','SWJG_DM','DHHM','ZYRS','DBR_YDDHHM','LSGXMC','ZZJGDM','SS_MC','XYDJ','SSHYDM','QYHGDM','SS_DM','NSRMC','XYPFFS','ZCZB_BZMC','SCJYQX_Z','DBRMC','DBR_ZJLX_MC','ZCZB','XYPFSJ','DBR_ZJLX_DM','SWJG_MC','DBR_ZJHM'],
    cn: ['登记注册类型代码','适用会计制度名称','经营范围','注册地电话号码','适用会计制度代码','纳税人状态代码','注册资本币种','纳税人状态名称','邮编','主管员','开业日期','所属行业名称','登记注册类型名称','纳税类型代码','注册地址','工商注册号','地市代码','纳税人识别号','行业门类代码','营业地址','行业门类名称','隶属关系代码','地市','核准登记日期','法定代表人电话号码','纳税类型名称','税务机构代码','电话号码','从业人数','法定代表人移动电话号码','隶属关系名称','组织机构代码','省市','信用等级','所属行业代码','企业海关代码','省份代码','纳税人名称','信用评分分数','注册资本币种名称','生产经营期止','法定代表人名称','法定代表人证件类型名称','注册资本','信用评分时间','法定代表证件类型代码','税务机构名称','法定代表人证件号码']
  },
  LXRXX_LIST: {
    name: '2.企业联系人信息(LXRXX_LIST)',
    en: ['DBR_DYDZ','DBRMC','DBR_DHHM','DBR_ZJLX_MC','DBR_ZJLX_DM','DBR_YDDHHM','BSSF','DBR_ZJHM','NSRSBH'],
    cn: ['代办人电子邮件','代办人名称','代办人电话号码','代办人证件类型名称','代办人证件类型代码','代办人移动电话号码','办税身份','代办人证件号码','纳税人识别号']
  },
  TZFXX_LIST: {
    name: '3.企业投资方信息(TZFXX_LIST)',
    en: ['TZJE','TZBL','GJDZ','ZJZLMC','ZJZLDM','TZFJJXZMC','NSRSBH','TZFJJXZDM','TZFMC','ZJHM'],
    cn: ['投资金额','投资比例','国际地址','证件种类名称','证件种类代码','投资方经济性质名称','纳税人识别号','投资方经济性质代码','投资方名称','证件号码']
  },
  SBXX_LIST: {
    name: '4.纳税申报数据(SBXX_LIST)',
    en: ['SSSQZ','SBRQ','ZSXMMC','YJSE','SSSQQ','QBXSE','YSXSSR','YNSE','SBQX','JMSE','YBTSE','ZSXMDM','NSRSBH'],
    cn: ['所属时间止','申报日期','征收项目名称','预缴税额','所属时间起','全部销售额','应税销售收入','应纳税额','申报期限','减免税额','应补退税额','征收项目代码','纳税人识别号']
  },
  ZSXX_LIST: {
    name: '5.税款征收信息(ZSXX_LIST)',
    en: ['SSSQ_Z','JKFSRQ','SKZL_DM','ZSXM_MC','SSSQ_Q','JKQX','SKZT_DM','ZXPM_DM','NSRMC','SE','SKZL_MC','XSSR','ZSXM_DM','SL','NSRSBH','SKZT_MC'],
    cn: ['所属时间止','缴款发生日期','税款种类代码','征收项目名称','所属时间起','缴款期限','税款状态代码','征收品目代码','纳税人名称','税额','税款种类名称','销售收入','征收项目代码','税率','纳税人识别号','税款状态名称']
  },
  ZCFZBXX_LIST: {
    name: '6.企业资产负债表(ZCFZBXX_LIST)',
    en: ['SKSSQQ','BBLX','XM','NCYE','MC','SKSSQZ','QMYE','NSRSBH','BSRQ'],
    cn: ['税款所属期起','报表类型','项目','年初余额','行次','税款所属期止','期末余额','纳税人识别号','报送日期']
  },
  LRBXX_LIST: {
    name: '7.企业利润表(LRBXX_LIST)',
    en: ['SKSSQQ','BBLX','XM','BQJE','MC','SKSSQZ','BYS','NSRSBH','BSRQ','SQJE'],
    cn: ['税款所属期起','报表类型','项目','本期金额','行次','税款所属期止','本月数','纳税识别号','报送日期','上期金额']
  },
  QYWFWZXX_LIST: {
    name: '8.企业涉税违法违规信息(QYWFWZXX_LIST)',
    en: ['NSRSBH','DJRQ','ZYWFWZSS','ZYWFWZSDDM','ZYWFWZSDMC','WFWZLXDM','WFWZLXMC','WFWZZTDM','WFWZZTMC','CLCFJDRQ','LARQ','XGZT','SSSQQ','SSSQZ'],
    cn: ['纳税人识别号','登记日期','主要违法违规事实','主要违法违规手段代码','主要违法违规手段名称','违法违规类型代码','违法违规类型名称','违法违规状态代码','违法违规状态名称','处理处罚决定日期','立案日期','修改状态','所属时期起','所属时期止']
  },
  SWJCXX_LIST: {
    name: '9.企业稽查信息(SWJCXX_LIST)',
    en: ['NSRSBH','AYDJRQ','AJLYDM','AJLYMC','WFWZLXDM','WFWZLXMC','JCLXDM','JCLXMC','JCZTDM','JCZTMC','AJCLYJDM','AJCLYJMC','AJMC','SSSQQ','SSSQZ'],
    cn: ['纳税人识别号','案源登记日期','案件来源代码','案件来源名称','违法违规类型代码','违法违规类型名称','稽查类型代码','稽查类型名称','稽查状态代码','稽查状态名称','案件处理意见代码','案件处理意见名称','案件名称','所属时期起','所属时期止']
  },
  QYBGDJXX_LIST: {
    name: '10.企业变更登记(QYBGDJXX_LIST)',
    en: ['NSRSBH','BGXMMC','BGXMDM','BGQNR','BGHNR','BGRQ'],
    cn: ['纳税人识别号','变更项目名称','变更项目代码','变更前内容','变更后内容','变更日期']
  }
};

// ========== 模版映射上传 ==========
const templateFile = document.getElementById('templateFile');
const uploadTemplateBtn = document.getElementById('uploadTemplateBtn');
const templateFileNameEl = document.getElementById('templateFileName');
const clearTemplateBtn = document.getElementById('clearTemplateBtn');
const mappingInfo = document.getElementById('mappingInfo');

uploadTemplateBtn?.addEventListener('click', () => { templateFile.click(); });

templateFile?.addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (!file) return;
  templateFileName = file.name;
  templateFileNameEl.textContent = file.name;
  clearTemplateBtn.style.display = 'inline-flex';
  showJsonInfo('正在解析模版映射关系...');
  const reader = new FileReader();
  reader.onload = (e) => {
    try {
      const data = new Uint8Array(e.target.result);
      const wb = XLSX.read(data, { type: 'array' });
      parseTemplateMapping(wb);
      showJsonInfo('模版映射加载成功！');
    } catch (err) {
      showJsonError('解析模版文件失败: ' + err.message);
    }
  };
  reader.readAsArrayBuffer(file);
});

clearTemplateBtn?.addEventListener('click', () => {
  fieldMapping = null;
  mappingStats = null;
  templateFileName = '';
  templateFile.value = '';
  templateFileNameEl.textContent = '未选择模版';
  clearTemplateBtn.style.display = 'none';
  mappingInfo.innerHTML = '<span class="mapping-badge empty">未加载映射 — 将使用原始JSON字段名</span>';
});

function parseTemplateMapping(wb) {
  fieldMapping = {};
  let totalMappings = 0;

  for (const sheetName of wb.SheetNames) {
    const ws = wb.Sheets[sheetName];
    const range = XLSX.utils.decode_range(ws['!ref'] || 'A1:A1');
    const numRows = range.e.r - range.s.r + 1;
    const numCols = range.e.c - range.s.c + 1;

    // ---- 方式1: 行优先（第1行=英文key, 第2行=中文label, 每列一对） ----
    const rowMajor = {};
    if (numRows >= 2) {
      for (let c = range.s.c; c <= range.e.c; c++) {
        const keyCell = ws[XLSX.utils.encode_cell({ r: 0, c: c })];
        const labelCell = ws[XLSX.utils.encode_cell({ r: 1, c: c })];
        if (keyCell && labelCell) {
          const key = String(keyCell.v || '').trim();
          const label = String(labelCell.v || '').trim();
          if (key && label && key !== label) {
            rowMajor[key] = label;
          }
        }
      }
    }

    // ---- 方式2: 列优先（第1列=英文key, 第2列=中文label, 从第2行开始跳过表头） ----
    const colMajor = {};
    if (numCols >= 2 && numRows >= 2) {
      for (let r = 1; r <= range.e.r; r++) {
        const keyCell = ws[XLSX.utils.encode_cell({ r: r, c: 0 })];
        const labelCell = ws[XLSX.utils.encode_cell({ r: r, c: 1 })];
        if (keyCell && labelCell) {
          const key = String(keyCell.v || '').trim();
          const label = String(labelCell.v || '').trim();
          if (key && label && key !== label) {
            colMajor[key] = label;
          }
        }
      }
    }

    // 自动选择映射数量更多的格式
    const rowCount = Object.keys(rowMajor).length;
    const colCount = Object.keys(colMajor).length;
    if (rowCount >= colCount) {
      Object.assign(fieldMapping, rowMajor);
      totalMappings += rowCount;
    } else {
      Object.assign(fieldMapping, colMajor);
      totalMappings += colCount;
    }
  }

  mappingStats = { sheetCount: wb.SheetNames.length, mappingCount: totalMappings };
  if (totalMappings > 0) {
    mappingInfo.innerHTML = '<span class="mapping-badge success">已加载 ' + totalMappings + ' 个字段映射</span>';
  } else {
    mappingInfo.innerHTML = '<span class="mapping-badge empty">模版中未找到有效映射 — 请确保模版格式为：第1行英文/第2行中文，或第1列英文/第2列中文</span>';
  }
}

function translateFieldName(engName) {
  if (!fieldMapping) { console.log('[translateFieldName] fieldMapping 为空，返回原始名称:', engName); return engName; }
  if (fieldMapping[engName]) { console.log('[translateFieldName] 完整匹配:', engName, '→', fieldMapping[engName]); return fieldMapping[engName]; }
  const parts = engName.split('.');
  const lastPart = parts[parts.length - 1];
  if (fieldMapping[lastPart]) {
    const prefixParts = parts.slice(0, -1);
    const translated = fieldMapping[lastPart];
    const result = prefixParts.length > 0 ? prefixParts.join('.') + '.' + translated : translated;
    console.log('[translateFieldName] 尾部匹配:', engName, '→', result);
    return result;
  }
  console.log('[translateFieldName] 无匹配，返回原始名称:', engName);
  return engName;
}

// ---- JSON Upload ----
document.getElementById('uploadJsonBtn')?.addEventListener('click', () => {
  document.getElementById('jsonFile').click();
});

document.getElementById('jsonFile')?.addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (!file) return;
  uploadedFileName = file.name;
  document.getElementById('jsonFileName').textContent = file.name;
  const reader = new FileReader();
  reader.onload = (e) => {
    document.getElementById('jsonInput').value = e.target.result;
    showJsonInfo('文件加载成功，请点击"处理数据"');
  };
  reader.readAsText(file);
});

// ---- Clear JSON Input ----
document.getElementById('clearJsonBtn')?.addEventListener('click', () => {
  document.getElementById('jsonInput').value = '';
  document.getElementById('jsonFile').value = '';
  document.getElementById('jsonFileName').textContent = '未选择文件';
  uploadedFileName = '';
  hideJsonMessages();
});

// ---- Reset JSON Tool ----
document.getElementById('resetJsonBtn')?.addEventListener('click', () => {
  document.getElementById('jsonInput').value = '';
  document.getElementById('jsonFile').value = '';
  document.getElementById('jsonFileName').textContent = '未选择文件';
  jsonWorkbook = null;
  jsonData = null;
  sheetDataMap.clear();
  uploadedFileName = '';
  fieldMapping = null;
  mappingStats = null;
  templateFileName = '';
  templateFile.value = '';
  templateFileNameEl.textContent = '未选择模版';
  clearTemplateBtn.style.display = 'none';
  document.getElementById('mappingInfo').innerHTML = '<span class="mapping-badge empty">未加载映射 — 将使用原始JSON字段名</span>';
  document.getElementById('downloadJsonBtn').disabled = true;
  hideJsonMessages();
  document.getElementById('jsonSheetList').innerHTML =
    '<div class="sheet-item"><span class="sheet-name">暂无数据</span><span class="sheet-rows">请先处理JSON数据</span></div>';
});

// ---- Process JSON Data ----
document.getElementById('processJsonBtn')?.addEventListener('click', async () => {
  const processBtn = document.getElementById('processJsonBtn');
  const downloadBtn = document.getElementById('downloadJsonBtn');
  try {
    const jsonText = document.getElementById('jsonInput').value.trim();
    if (!jsonText) { showJsonError('请输入JSON数据'); return; }

    showJsonInfo('正在解析JSON...');
    processBtn.disabled = true;
    downloadBtn.disabled = true;

    // 先让 UI 更新加载状态
    await sleep(50);

    jsonData = JSON.parse(jsonText);
    showJsonInfo('正在处理数据，请稍候...');
    await sleep(30);

    jsonWorkbook = await processJsonDataAsync(jsonData);

    downloadBtn.disabled = false;
    displaySheetInfo();
    showJsonSuccess('数据处理成功！可以下载Excel文件了。');
  } catch (err) {
    showJsonError('处理失败: ' + err.message);
  } finally {
    processBtn.disabled = false;
  }
});

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ---- Download Excel ----
document.getElementById('downloadJsonBtn')?.addEventListener('click', () => {
  if (!jsonWorkbook || sheetDataMap.size === 0) {
    showJsonError('请先处理JSON数据');
    return;
  }
  const wb = XLSX.utils.book_new();
  sheetDataMap.forEach((data, sheetKey) => {
    const meta = TAX_SHEET_META[sheetKey];

    if (meta && meta.en && meta.cn && data.length > 0) {
      // 已知税务sheet：第1行英文表头 + 第2行中文表头 + 数据行
      const aoa = [meta.en, meta.cn];
      for (const row of data) {
        const rowArr = meta.en.map(function(k) {
          const v = row[k];
          return v !== undefined && v !== null ? v : '';
        });
        aoa.push(rowArr);
      }
      const ws = XLSX.utils.aoa_to_sheet(aoa);
      XLSX.utils.book_append_sheet(wb, ws, meta.name);
    } else if (fieldMapping && data.length > 0) {
      // 有自定义模版映射：尝试构建双行表头
      const enHeaders = Object.keys(data[0]);
      const cnHeaders = enHeaders.map(function(k) { return fieldMapping[k] || k; });
      const hasTranslation = cnHeaders.some(function(h, i) { return h !== enHeaders[i]; });
      if (hasTranslation) {
        const aoa = [enHeaders, cnHeaders];
        for (const row of data) {
          const rowArr = enHeaders.map(function(k) {
            const v = row[k];
            return v !== undefined && v !== null ? v : '';
          });
          aoa.push(rowArr);
        }
        const ws = XLSX.utils.aoa_to_sheet(aoa);
        XLSX.utils.book_append_sheet(wb, ws, sheetKey);
      } else {
        const ws = XLSX.utils.json_to_sheet(data);
        XLSX.utils.book_append_sheet(wb, ws, sheetKey);
      }
    } else {
      // 无映射：单行英文表头
      const ws = XLSX.utils.json_to_sheet(data);
      XLSX.utils.book_append_sheet(wb, ws, sheetKey);
    }
  });
  const excelBuffer = XLSX.write(wb, { bookType: 'xlsx', type: 'array' });
  const blob = new Blob([excelBuffer], { type: 'application/octet-stream' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  const xlsxName = uploadedFileName ? uploadedFileName.replace(/\.json$/i, '.xlsx') : ('json_export_' + new Date().toISOString().slice(0, 10) + '.xlsx');
  a.download = xlsxName;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showJsonSuccess('下载成功！');
});

// ---- 通用JSON数据处理（异步分块） ----
async function processJsonDataAsync(data) {
  sheetDataMap.clear();
  const usedSheetNames = new Set();
  console.log('[processJsonDataAsync] 开始处理，fieldMapping 是否已加载:', fieldMapping ? Object.keys(fieldMapping).length + '个映射' : '未加载(null)');

  if (Array.isArray(data)) {
    if (data.length === 0) throw new Error('JSON数组为空，没有数据可处理');
    if (!isObjectOrArray(data[0])) {
      const rows = data.map((v, i) => ({ '序号': i + 1, '值': v }));
      sheetDataMap.set(uniqueSheetName('数据', usedSheetNames), rows);
    } else if (isObject(data[0])) {
      await processArrayOfObjectsAsync(data, '数据', usedSheetNames);
    }
  } else if (isObject(data)) {
    await processObjectToSheetsAsync(data, usedSheetNames);
  } else {
    throw new Error('不支持的JSON数据类型：仅支持对象或数组');
  }

  if (sheetDataMap.size === 0) sheetDataMap.set('数据', []);
  return true;
}

function isObject(v) { return typeof v === 'object' && v !== null && !Array.isArray(v); }
function isObjectOrArray(v) { return typeof v === 'object' && v !== null; }

function flattenObject(obj, prefix) {
  const result = {};
  for (const [key, value] of Object.entries(obj)) {
    const newKey = prefix ? prefix + '.' + key : key;
    if (isObject(value)) {
      Object.assign(result, flattenObject(value, newKey));
    } else if (!Array.isArray(value)) {
      result[newKey] = value;
    }
  }
  return result;
}

function uniqueSheetName(base, used) {
  let name = base.length > 31 ? base.slice(0, 31) : base;
  if (!used.has(name)) { used.add(name); return name; }
  let n = 2;
  while (true) {
    let s = (base.slice(0, 27) + '_' + n).slice(0, 31);
    if (!used.has(s)) { used.add(s); return s; }
    n++;
  }
}

async function processArrayOfObjectsAsync(arr, sheetName, usedNames) {
  const CHUNK_SIZE = 200;

  // 扫描所有层级中的数组路径
  const arrayPaths = new Map();
  function scanArrays(obj, prefix) {
    for (const [key, value] of Object.entries(obj)) {
      const path = prefix ? prefix + '.' + key : key;
      if (Array.isArray(value)) arrayPaths.set(path, key);
      else if (isObject(value)) scanArrays(value, path);
    }
  }
  if (arr.length > 0 && isObject(arr[0])) scanArrays(arr[0], '');

  // 收集根级对象key（如FPXX）分别建sheet
  const rootObjectCollectors = {};
  const rootArrayCollectors = {};
  const rootScalarCollectors = {};
  if (arr.length > 0 && isObject(arr[0])) {
    for (const [key, value] of Object.entries(arr[0])) {
      if (isObject(value)) rootObjectCollectors[key] = [];
      else if (Array.isArray(value)) rootArrayCollectors[key] = [];
      else rootScalarCollectors[key] = [];
    }
  }

  const collectors = {};
  arrayPaths.forEach((key, path) => { collectors[path] = []; });

  // 递归遍历嵌套对象，收集深层数组数据到 collectors
  function walkNestedArrays(obj, prefix, rowIndex) {
    for (const [key, value] of Object.entries(obj)) {
      const path = prefix ? prefix + '.' + key : key;
      if (Array.isArray(value)) {
        if (collectors[path]) {
          value.forEach(sub => {
            if (isObject(sub)) {
              const enriched = flattenObject(sub, '');
              collectors[path].push(enriched);
            } else {
              collectors[path].push({ [key]: sub });
            }
          });
        }
      } else if (isObject(value)) {
        walkNestedArrays(value, path, rowIndex);
      }
    }
  }

  const total = arr.length;

  // 分块处理，每块后 yield 让 UI 保持响应
  for (let start = 0; start < total; start += CHUNK_SIZE) {
    const end = Math.min(start + CHUNK_SIZE, total);

    for (let i = start; i < end; i++) {
      const item = arr[i];

      // 按根级key分别收集数据
      for (const [key, value] of Object.entries(item)) {
        if (isObject(value)) {
          if (rootObjectCollectors[key] !== undefined) {
            const flat = flattenObject(value, '');
            walkNestedArrays(value, key, i);
            rootObjectCollectors[key].push(flat);
          }
        } else if (Array.isArray(value)) {
          if (collectors[key]) {
            value.forEach(sub => {
              if (isObject(sub)) {
                const enriched = flattenObject(sub, '');
                collectors[key].push(enriched);
              } else {
                collectors[key].push({ [key]: sub });
              }
            });
          }
        } else {
          if (rootScalarCollectors[key] !== undefined) {
            rootScalarCollectors[key].push({ [key]: value });
          }
        }
      }
    }

    // 每处理一个 chunk 让出主线程，更新加载提示
    if (start + CHUNK_SIZE < total) {
      showJsonInfo('正在处理数据... ' + Math.min(end, total) + '/' + total + ' 行');
      await sleep(0);
    }
  }

  const hasNestedStructure = Object.keys(rootObjectCollectors).length > 0 || arrayPaths.size > 0;

  if (!hasNestedStructure) {
    // 所有条目只有标量字段 → 应用字段映射后建表
    const mappedArr = arr.map(item => {
      const mapped = {};
      for (const [k, v] of Object.entries(item)) {
        mapped[k] = v;
      }
      return mapped;
    });
    sheetDataMap.set(uniqueSheetName(sheetName, usedNames), mappedArr);
  } else {
    // 只为根级对象key建sheet（如FPXX）
    Object.entries(rootObjectCollectors).forEach(([key, items]) => {
      if (items.length > 0) {
        sheetDataMap.set(uniqueSheetName(key, usedNames), items);
      }
    });

    // 根级标量
    const scalarItems = [];
    Object.entries(rootScalarCollectors).forEach(([key, items]) => {
      if (items.length > 0) scalarItems.push(...items);
    });
    if (scalarItems.length > 0) {
      sheetDataMap.set(uniqueSheetName(sheetName + '_标量', usedNames), scalarItems);
    }

    // 子数组建子sheet
    arrayPaths.forEach((key, path) => {
      const items = collectors[path];
      const nName = uniqueSheetName(key, usedNames);
      sheetDataMap.set(nName, items.length > 0 ? items : []);
    });
  }
}

async function processObjectToSheetsAsync(obj, usedNames, parentKey) {
  const entries = Object.entries(obj);
  const arrayEntries = entries.filter(([, v]) => Array.isArray(v));
  const objectEntries = entries.filter(([, v]) => isObject(v));
  const scalarEntries = entries.filter(([, v]) => !Array.isArray(v) && !isObject(v));

  for (const [key, arr] of arrayEntries) {
    if (arr.length > 0 && isObject(arr[0])) {
      await processArrayOfObjectsAsync(arr, key, usedNames);
    } else if (arr.length > 0) {
      sheetDataMap.set(uniqueSheetName(key, usedNames),
        arr.map((v, i) => ({ '序号': i + 1, '值': v })));
    } else {
      sheetDataMap.set(uniqueSheetName(key, usedNames), []);
    }
  }

  for (const [key, obj] of objectEntries) {
    // 检查是否为扁平对象（所有值都是标量，如NSRJCXX）→ 作为一行记录处理
    const subEntries = Object.entries(obj);
    const hasNested = subEntries.some(([, v]) => isObject(v) || Array.isArray(v));
    if (!hasNested) {
      const flat = {};
      for (const [k, v] of subEntries) {
        flat[k] = v;
      }
      sheetDataMap.set(uniqueSheetName(key, usedNames), [flat]);
    } else {
      await processObjectToSheetsAsync(obj, usedNames, key);
    }
  }

  if (scalarEntries.length > 0) {
    const rows = scalarEntries.map(([k, v]) => ({ '字段': translateFieldName(k), '值': v }));
    sheetDataMap.set(uniqueSheetName(parentKey || '根节点', usedNames), rows);
  }
}

// ---- Display Sheet Info ----
function displaySheetInfo() {
  let html = '';
  sheetDataMap.forEach((data, key) => {
    html += `<div class="sheet-item"><span class="sheet-name">${key}</span><span class="sheet-rows">${data.length} 行数据</span></div>`;
  });
  document.getElementById('jsonSheetList').innerHTML = html;
}


// ---- JSON Message Helpers ----
function showJsonError(msg) {
  const el = document.getElementById('jsonErrorMsg');
  el.textContent = msg; el.style.display = 'block';
  document.getElementById('jsonSuccessMsg').style.display = 'none';
  document.getElementById('jsonInfoMsg').style.display = 'none';
}
function showJsonSuccess(msg) {
  const el = document.getElementById('jsonSuccessMsg');
  el.textContent = msg; el.style.display = 'block';
  document.getElementById('jsonErrorMsg').style.display = 'none';
  document.getElementById('jsonInfoMsg').style.display = 'none';
}
function showJsonInfo(msg) {
  const el = document.getElementById('jsonInfoMsg');
  el.textContent = msg; el.style.display = 'block';
}
function hideJsonMessages() {
  document.getElementById('jsonErrorMsg').style.display = 'none';
  document.getElementById('jsonSuccessMsg').style.display = 'none';
  document.getElementById('jsonInfoMsg').style.display = 'none';
}

// ==========================================
// Report Search - 报表查询
// ==========================================
var reportColumns = [];
var reportRows = [];

// 表头中文映射
var REPORT_COL_LABELS = {
  'sql_content': 'SQL内容',
  'report_mod_id': '报表模型ID',
  'report_mod_mc': '报表模型名称',
  'parent_mod_mc': '父模型名称',
  'create_user': '创建人',
  'create_time': '创建时间'
};

document.getElementById('reportSearchForm')?.addEventListener('submit', async function(e) {
  e.preventDefault();
  var result = document.getElementById('reportResult');
  var keyword = document.getElementById('report_keyword').value.trim();

  if (!keyword) {
    showResult(result, 'error', '请输入搜索关键词');
    return;
  }

  showResult(result, 'loading', '正在查询...');
  document.getElementById('reportTableCard').style.display = 'none';

  try {
    var res = await apiFetch('/api/report/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ keyword: keyword })
    });
    var data = await res.json();

    if (data.success) {
      reportColumns = data.columns || [];
      reportRows = data.rows || [];
      showResult(result, 'success', '查询完成，共找到 ' + data.count + ' 条记录');
      renderReportTable(reportColumns, reportRows, data.count);
    } else {
      showResult(result, 'error', data.error || '查询失败');
    }
  } catch (err) {
    showResult(result, 'error', '请求失败: ' + err.message);
  }
});

function renderReportTable(columns, rows, count) {
  var card = document.getElementById('reportTableCard');
  var wrapper = document.getElementById('reportTableWrapper');
  var countEl = document.getElementById('reportCount');

  countEl.textContent = count + ' 条';
  card.style.display = '';

  if (!rows || rows.length === 0) {
    wrapper.innerHTML = '<p style="padding:20px;color:var(--text-muted);text-align:center;">未找到匹配的记录</p>';
    return;
  }

  var html = '<table class="preview-table"><thead><tr>';
  for (var i = 0; i < columns.length; i++) {
    var col = columns[i];
    var label = REPORT_COL_LABELS[col] || col.toUpperCase();
    html += '<th>' + escapeHtml(label) + '</th>';
  }
  html += '</tr></thead><tbody>';

  for (var r = 0; r < rows.length; r++) {
    html += '<tr>';
    for (var c = 0; c < columns.length; c++) {
      var val = rows[r][columns[c]];
      if (val === null || val === undefined) val = '';
      else val = String(val);
      html += '<td title="' + escapeHtml(val) + '">' + escapeHtml(val) + '</td>';
    }
    html += '</tr>';
  }
  html += '</tbody></table>';
  wrapper.innerHTML = html;
}

function escapeHtml(str) {
  var div = document.createElement('div');
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}
