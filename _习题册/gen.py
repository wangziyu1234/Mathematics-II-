#!/usr/bin/env python3
import re, os, sys, subprocess

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))   # 脚本所在目录（_习题册）
SRC = os.path.dirname(HERE)                          # 仓库根目录（含各年 MD）
OUT = HERE
os.makedirs(OUT, exist_ok=True)
XEL = r"C:\texlive\2026\bin\windows\xelatex.exe"

PREAMBLE = r"""\documentclass[UTF8,12pt]{ctexart}
\usepackage[paperwidth=240mm,paperheight=200mm,margin=14mm,top=8mm]{geometry}
\usepackage{amsmath,amssymb,mathtools}
\usepackage{xcolor}
\pagestyle{empty}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}
\newcommand{\qn}[1]{\textbf{\large #1}\ }
\xeCJKDeclareCharClass{CJK}{"2460 -> "24FF}
\begin{document}
"""
POST = r"\end{document}"

def md_to_latex(s):
    s = s.replace('&emsp;', '\\qquad')
    s = re.sub(r'\*\*([^*]*)\*\*', r'\\textbf{\1}', s)
    s = re.sub(r'<!--.*?-->', '', s, flags=re.S)
    return s

def parse_year(path):
    lines = open(path, encoding='utf-8').read().split('\n')
    qs = []
    cur_num = None; cur = []; seen_nn = False; in_ans = False; g = 0
    for ln in lines:
        s = ln.strip()
        if not s:
            if cur_num is not None: cur.append('')
            continue
        if s.startswith('## 参考'):
            in_ans = True; continue
        if in_ans or s.startswith('#') or s.startswith('>') or s.startswith('---'):
            continue
        if s.startswith('<!--'):
            continue
        m_mod = re.match(r'^(\d+)[\.、]\s*(.*)$', s)
        m_old = re.match(r'^[(（](\d+)[)）]\s*(.*)$', s)
        start = False; num = None; rest = None
        if m_mod:
            seen_nn = True; num = m_mod.group(1); rest = m_mod.group(2); start = True
        elif m_old and not seen_nn:
            num = m_old.group(1); rest = m_old.group(2); start = True
        if start:
            if cur_num is not None:
                g += 1; qs.append((g, cur))
            cur_num = num; cur = [rest]
            continue
        if cur_num is not None:
            cur.append(s)
    if cur_num is not None:
        g += 1; qs.append((g, cur))
    return qs

def build_latex(year, qs):
    body = []
    for n, content in qs:
        lines = []
        for cl in content:
            t = md_to_latex(cl).strip()
            if not t: continue
            if re.match(r'^[(（][A-Da-d][)）]', t):
                lines.append('\\\\\n\\noindent ' + t)
            elif re.match(r'^[（(][一二三四ⅠⅡⅢⅰⅱⅲ1-9][)）]', t) or re.match(r'^\([一二三四1-4]\)', t):
                lines.append('\\\\\n' + t)
            else:
                lines.append(t)
        body.append('\\qn{%s.%d}\n%s\n\n\\vfill\n\\newpage' % (year, n, '\n'.join(lines)))
    return PREAMBLE + '\n'.join(body) + '\n' + POST

def make(year):
    path = os.path.join(SRC, f"{year}年考研数学二试题.md")
    if not os.path.exists(path):
        print(f"{year}: missing source"); return None
    qs = parse_year(path)
    tex = build_latex(year, qs)
    texpath = os.path.join(OUT, f"{year}.tex")
    open(texpath, 'w', encoding='utf-8').write(tex)
    r = subprocess.run([XEL, '-interaction=nonstopmode', os.path.basename(texpath)],
                       cwd=OUT, capture_output=True, text=True, encoding='utf-8', errors='replace')
    pdf = texpath[:-4] + '.pdf'
    ok = os.path.exists(pdf)
    return len(qs), ok

if __name__ == '__main__':
    for y in sys.argv[1:]:
        r = make(y)
        if r: print(f"{y}: {r[0]} questions -> {'OK' if r[1] else 'FAIL'}")
