# -*- coding: utf-8 -*-
"""
gen_violation_html.py - 违规通知 txt → 静态 HTML 索引 (0 端口, GitHub Pages 友好)

输入: 当前目录 (G:/餐补/chaxungonggao) 下所有 *.txt (用户手动复制进来)
输出: index.html (内嵌所有数据, 浏览器打开/部署 GitHub Pages 都能用)

特性:
  - 解析 ✂ 分隔线切的违规通知条目
  - 群名匹配 G:\餐补\群组映射表.json (查询群子集), 匹配上显示 telegram.me/c/chat_id 链接
  - 智能匹配: 去前缀 (N-)、去后缀 (查询群/查詢群)、空格正规化
  - 通知文本默认折叠 1 行 preview, 点击展开
  - 一键复制按钮: navigator.clipboard.writeText(content), 自动跳过 ✂ 分隔线
  - 顶部 sticky 搜索栏: 按群名/地址/触发项过滤
  - 表格三色按钮 (跟 G:\餐补\index.html 一致): 复制蓝 / 跳转橙 / 复制短链绿

用法:
  cd G:/餐补/chaxungonggao
  python -X utf8 gen_violation_html.py
  python -X utf8 gen_violation_html.py --txt MMDD.txt   # 只处理单个文件
"""
import os
import re
import sys
import json
import html
import argparse
import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = Path(__file__).resolve().parent
MAPPING = Path(r'G:\餐补\群组映射表.json')
OUTPUT = ROOT / 'index.html'

# 群名去前缀/后缀 + 模糊归一
_PREFIX_RE = re.compile(r'^\s*\d{1,3}\s*[-－]\s*')
_SUFFIXES = ['查询群', '查詢群', '查询', '查詢']


def normalize_group(name):
    """智能归一群名: 去前缀 N- + 去后缀 查询群/查詢群 + 空格归一"""
    if not name:
        return ''
    s = name.strip()
    s = _PREFIX_RE.sub('', s)
    for suf in _SUFFIXES:
        if s.endswith(suf):
            s = s[:-len(suf)].strip()
    s = re.sub(r'\s+', ' ', s)
    return s


def load_mapping():
    """读群组映射表, 返回 {(group_name_normalized): chat_id}  + {(exact_title): chat_id}"""
    if not MAPPING.exists():
        return {}, {}
    with MAPPING.open(encoding='utf-8') as f:
        raw = json.load(f)
    # raw: {title: {chat_id, type, ...}}
    exact = {}  # 原 title -> chat_id (只保留查询群)
    norm = {}   # 归一后 -> chat_id
    for title, info in raw.items():
        if '查询' not in title and '查詢' not in title:
            continue
        cid = info.get('chat_id')
        if not cid:
            continue
        exact[title] = str(cid)
        # 归一 (用 normalize_group, 但同时去括号内容差异)
        n = normalize_group(title)
        if n and n not in norm:
            norm[n] = str(cid)
    return exact, norm


def parse_one(txt_path: Path):
    """解析单个 .txt, 返回 [(idx, total, target, group, addr, trigger_n, content), ...]"""
    text = txt_path.read_text(encoding='utf-8')
    parts = re.split(r'\n?✂\s*─+\s*第\s*(\d+)\s*/\s*(\d+)\s*条.*?发送至：([^\n─]+)', text)
    items = []
    for i in range(1, len(parts), 4):
        idx_s, total_s, target_s, content = parts[i], parts[i+1], parts[i+2], parts[i+3]
        try:
            idx, total = int(idx_s), int(total_s)
        except ValueError:
            continue
        target = target_s.strip()
        m_group = re.search(r'👥 查询群：([^\n]+)', content)
        m_addr = re.search(r'🔗 地址：(0x[0-9a-fA-F]{40})', content)
        m_count = re.search(r'❌ 本次触发 (\d+) 项', content)
        items.append({
            'idx': idx,
            'total': total,
            'target': target,
            'group': m_group.group(1).strip() if m_group else None,
            'addr': m_addr.group(1) if m_addr else None,
            'trigger_n': int(m_count.group(1)) if m_count else 0,
            # 通知正文: 从 "⚠️ 818共识..." 开始到末尾 (去掉 ✂ 残尾)
            'content': content.strip(),
            'source_file': txt_path.name,
        })
    return items


def match_group(group_name, exact, norm):
    """群名 → chat_id 智能匹配"""
    if not group_name:
        return None, 'empty'
    # 1) 精确 (含前后缀)
    if group_name in exact:
        return exact[group_name], 'exact'
    # 2) 归一后查 norm
    n = normalize_group(group_name)
    if not n or len(n) < 2 or n in ('-', '_', '?', '？', '无', '空'):
        # 群名是占位符 (-/?/空), 跳过 fuzzy (否则 "-" 是任何字符串子串会误匹配)
        return None, 'placeholder'
    if n in norm:
        return norm[n], 'normalized'
    # 3) 模糊: 归一后 substring (双向)
    candidates = []
    for title_norm, cid in norm.items():
        if title_norm == n:
            continue
        if len(title_norm) < 2:
            continue
        if n in title_norm or title_norm in n:
            candidates.append((title_norm, cid))
    if candidates:
        # 取最短匹配 (越精确越好)
        candidates.sort(key=lambda x: len(x[0]))
        return candidates[0][1], f'fuzzy:{candidates[0][0]}'
    return None, 'no-match'


def chat_id_to_tg_url(chat_id):
    """chat_id (TG Channel/Supergroup, -100xxx) → telegram.me/c/xxx"""
    s = str(chat_id)
    if s.startswith('-100'):
        return f'https://telegram.me/c/{s[4:]}'
    if s.startswith('-'):
        return f'https://telegram.me/c/{s[1:]}'
    return f'https://telegram.me/c/{s}'


def render_html(items, source_files):
    """渲染 index.html"""
    # 通知日期从 source_file 推断 (MMDD.txt)
    date_label = source_files[0].replace('.txt', '') if source_files else ''
    today = datetime.date.today().isoformat()

    rows_html = []
    for it in items:
        idx, total = it['idx'], it['total']
        target = it['target']
        group = it['group'] or '-'
        addr = it['addr'] or ''
        trigger_n = it['trigger_n']
        content = it['content']
        chat_id, match_type = match_group(group, EXACT, NORM)
        if chat_id:
            tg_url = chat_id_to_tg_url(chat_id)
            group_cell = f'<a class="group-link" href="{tg_url}" target="_blank" rel="noopener">{html.escape(group)}</a>'
            jump_btn = f'<a class="copy-group-btn" href="{tg_url}" target="_blank" rel="noopener">跳转群</a>'
        else:
            group_cell = f'{html.escape(group)} <span class="badge-no-match">❌ {match_type}</span>'
            jump_btn = f'<span class="copy-group-btn disabled" title="群名未匹配映射表">未匹配</span>'
        addr_short = (addr[:8] + '…' + addr[-6:]) if addr else '-'
        addr_full = html.escape(addr)
        # 触发项数 + 颜色
        trigger_color = '#1d6f3a' if trigger_n == 0 else ('#c77700' if trigger_n == 1 else '#c0392b')
        # 通知正文: 转义后存到 data-attr, 默认显示前 80 字
        content_escaped = html.escape(content)
        preview = content.split('\n')[1] if '\n' in content else content[:80]
        preview_esc = html.escape(preview.strip()[:80])
        # 复制按钮: 复制纯 content (不含 ✂ 分隔线)
        content_for_copy = content  # content 已经是剥离 ✂ 后的纯通知
        copy_btn = f'<button class="copy-btn" data-copy="{html.escape(content)}">复制通知</button>'

        rows_html.append(f'''
<tr data-group="{html.escape(group)}" data-addr="{addr_full}" data-trigger="{trigger_n}">
  <td class="idx">{idx}/{total}</td>
  <td class="group-cell">{group_cell}</td>
  <td class="addr" title="{addr_full}">{addr_short}</td>
  <td class="trigger" style="color:{trigger_color};font-weight:600">{trigger_n}</td>
  <td class="target">→ {html.escape(target)}</td>
  <td class="content-cell">
    <details><summary>{preview_esc}</summary><pre class="content-full">{content_escaped}</pre></details>
  </td>
  <td class="actions">{jump_btn}{copy_btn}</td>
</tr>''')

    rows_str = '\n'.join(rows_html)

    # 群名匹配统计
    matched_n = sum(1 for it in items if match_group(it['group'] or '', EXACT, NORM)[0])
    total_n = len(items)

    html_doc = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>违规通知下发索引 - {html.escape(date_label)}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
         margin: 0; padding: 16px; background: #f5f5f7; color: #1d1d1f; }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  .meta {{ color: #6e6e73; font-size: 13px; margin-bottom: 12px; }}
  .search-bar {{ position: sticky; top: 0; background: rgba(245,245,247,0.95);
                 backdrop-filter: blur(8px); padding: 12px 0; margin-bottom: 12px;
                 border-bottom: 1px solid #d2d2d7; z-index: 10; }}
  .search-bar input {{ width: 100%; max-width: 600px; padding: 10px 14px; font-size: 15px;
                       border: 1px solid #d2d2d7; border-radius: 8px; background: #fff; outline: none; }}
  .search-bar input:focus {{ border-color: #0071e3; box-shadow: 0 0 0 3px rgba(0,113,227,0.15); }}
  .stats {{ margin-left: 12px; color: #6e6e73; font-size: 13px; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px;
           overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }}
  th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #f0f0f3;
            font-size: 13px; vertical-align: top; }}
  th {{ background: #fafafc; font-weight: 600; color: #6e6e73; font-size: 12px;
        text-transform: uppercase; letter-spacing: 0.5px; }}
  tr:hover td {{ background: #f8f9fb; }}
  .addr {{ font-family: "SF Mono", Consolas, monospace; font-size: 12px; color: #6e6e73; }}
  .idx {{ color: #6e6e73; font-size: 12px; font-weight: 500; white-space: nowrap; }}
  .target {{ color: #6e6e73; font-size: 12px; white-space: nowrap; }}
  .content-cell {{ max-width: 380px; }}
  .content-cell details summary {{ cursor: pointer; color: #6e6e73; font-size: 12px;
                                    padding: 2px 0; outline: none; }}
  .content-cell details summary:hover {{ color: #0071e3; }}
  .content-cell details[open] summary {{ color: #1d1d1f; font-weight: 500; margin-bottom: 6px; }}
  .content-full {{ background: #f8f9fb; padding: 10px; border-radius: 6px;
                   font-size: 12px; line-height: 1.5; white-space: pre-wrap;
                   word-wrap: break-word; max-height: 400px; overflow-y: auto;
                   font-family: "SF Mono", Consolas, monospace; }}
  .actions {{ white-space: nowrap; }}
  .group-link {{ color: #1d1d1f; font-weight: 500; text-decoration: none; border-bottom: 1px dashed #d2d2d7; }}
  .group-link:hover {{ color: #0071e3; border-bottom-color: #0071e3; }}
  .badge-no-match {{ display: inline-block; padding: 1px 5px; border-radius: 3px;
                     font-size: 10px; background: #ffe4e1; color: #c0392b; margin-left: 4px; }}
  .empty {{ padding: 40px; text-align: center; color: #999; }}
  .copy-btn {{ background: #0071e3; color: #fff; border: none; border-radius: 5px;
               padding: 5px 10px; font-size: 12px; cursor: pointer;
               white-space: nowrap; transition: background-color 0.15s;
               min-width: 78px; box-sizing: border-box; text-align: center; margin-left: 4px; }}
  .copy-btn:hover {{ background: #005bb5; }}
  .copy-btn.copied {{ background: #28a745; }}
  .copy-group-btn {{ background: linear-gradient(135deg, #ff9500 0%, #ff6b00 100%);
                     color: #fff; border: none; border-radius: 5px;
                     padding: 5px 10px; font-size: 12px; cursor: pointer;
                     white-space: nowrap; box-shadow: 0 1px 3px rgba(255,107,0,0.4);
                     min-width: 78px; box-sizing: border-box; text-align: center;
                     text-decoration: none; display: inline-block; }}
  .copy-group-btn::before {{ content: '🏠'; margin-right: 3px;
                              filter: drop-shadow(0 1px 1px rgba(0,0,0,0.2)); }}
  .copy-group-btn:hover {{ background: linear-gradient(135deg, #ffaa33 0%, #ff8000 100%); }}
  .copy-group-btn.disabled {{ background: #e8e8ed; color: #999; cursor: not-allowed;
                             box-shadow: none; }}
  .copy-group-btn.disabled::before {{ content: '❌'; }}
</style>
</head>
<body>
<h1>📢 违规通知下发索引</h1>
<div class="meta">
  源文件: {', '.join(html.escape(f) for f in source_files)} ·
  共 <strong>{total_n}</strong> 条 ·
  群名匹配: <strong>{matched_n}/{total_n}</strong> ({100*matched_n//total_n if total_n else 0}%) ·
  生成时间: {today}
</div>
<div class="search-bar">
  <input type="text" id="search" placeholder="搜索 群名 / 地址 / 触发项 / 发送至..." autofocus>
  <span class="stats" id="stats"></span>
</div>
<table>
<thead><tr>
  <th>#</th><th>查询群</th><th>地址</th><th>触发项</th><th>发送至</th><th>通知预览</th><th>操作</th>
</tr></thead>
<tbody id="rows">
{rows_str}
</tbody>
</table>
<div id="empty" class="empty" style="display:none">无匹配结果</div>
<script>
  // 复制通知 (跳过 ✂ 分隔线 - 但 content 已经是剥离后的纯通知, 直接复制)
  document.querySelectorAll('.copy-btn').forEach(btn => {{
    btn.addEventListener('click', async () => {{
      const text = btn.getAttribute('data-copy');
      try {{
        await navigator.clipboard.writeText(text);
        const orig = btn.textContent;
        btn.textContent = '✓ 已复制';
        btn.classList.add('copied');
        setTimeout(() => {{ btn.textContent = orig; btn.classList.remove('copied'); }}, 1500);
      }} catch (e) {{
        // 降级: 旧浏览器
        const ta = document.createElement('textarea');
        ta.value = text; document.body.appendChild(ta);
        ta.select(); document.execCommand('copy'); document.body.removeChild(ta);
        btn.textContent = '✓ 已复制';
        btn.classList.add('copied');
        setTimeout(() => {{ btn.textContent = '复制通知'; btn.classList.remove('copied'); }}, 1500);
      }}
    }});
  }});

  // 搜索过滤
  const search = document.getElementById('search');
  const rows = document.querySelectorAll('#rows tr');
  const stats = document.getElementById('stats');
  const empty = document.getElementById('empty');
  function filterRows() {{
    const q = search.value.trim().toLowerCase();
    let shown = 0;
    rows.forEach(r => {{
      const hay = (r.dataset.group + ' ' + r.dataset.addr + ' ' + r.dataset.trigger).toLowerCase();
      const show = !q || hay.includes(q);
      r.style.display = show ? '' : 'none';
      if (show) shown++;
    }});
    stats.textContent = shown < rows.length ? `${{shown}} / ${{rows.length}}` : '';
    empty.style.display = (shown === 0) ? 'block' : 'none';
  }}
  search.addEventListener('input', filterRows);
</script>
</body>
</html>
'''
    return html_doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--txt', default=None, help='只处理单个 .txt 文件 (默认: 当前目录下所有 *.txt)')
    ap.add_argument('--mapping', default=str(MAPPING))
    args = ap.parse_args()

    global EXACT, NORM
    EXACT, NORM = load_mapping()
    print(f'[*] 群组映射: {len(EXACT)} 个查询群 (精确), {len(NORM)} 个 (归一后)')

    if args.txt:
        txt_files = [ROOT / args.txt]
    else:
        txt_files = sorted(ROOT.glob('*.txt'))
    if not txt_files:
        print(f'X  当前目录没找到 .txt: {ROOT}')
        return

    all_items = []
    for f in txt_files:
        items = parse_one(f)
        print(f'[*] {f.name}: 解析 {len(items)} 条')
        all_items.extend(items)

    # 按 idx 排序
    all_items.sort(key=lambda x: (x.get('source_file', ''), x['idx']))

    source_files = [f.name for f in txt_files]
    html_doc = render_html(all_items, source_files)
    OUTPUT.write_text(html_doc, encoding='utf-8')

    matched = sum(1 for it in all_items if match_group(it['group'] or '', EXACT, NORM)[0])
    print(f'[OK] {len(all_items)} 条 ({matched} 匹配, {len(all_items)-matched} 未匹配)')
    print(f'[OK] 输出: {OUTPUT} ({OUTPUT.stat().st_size:,} bytes)')


if __name__ == '__main__':
    main()
