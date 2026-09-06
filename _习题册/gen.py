#!/usr/bin/env python3
from pathlib import Path
import argparse
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
XELATEX = shutil.which('xelatex') or r'C:\texlive\2026\bin\windows\xelatex.exe'
QUESTION = re.compile(r'^(?:###\s*)?(?:\*\*)?\s*(?:[(（](\d+)[)）]|(\d+)[.、．])\s*(?:\*\*)?', re.M)
PREAMBLE = r'''\documentclass[UTF8,12pt,fontset=windows]{ctexart}
\usepackage[paperwidth=240mm,paperheight=200mm,left=14mm,right=14mm,top=9mm,bottom=12mm]{geometry}
\usepackage{amsmath,amssymb,mathtools,bm,graphicx,xcolor}
\pagestyle{empty}
\setlength{\parindent}{0pt}
\setlength{\parskip}{4pt}
\setlength{\emergencystretch}{2em}
\xeCJKDeclareCharClass{CJK}{"2460 -> "24FF}
\xeCJKDeclareCharClass{CJK}{"2160 -> "2188}
\begin{document}
'''

def questions_from_text(text):
    text = re.split(r'^##\s*参考', text, flags=re.M)[0]
    text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
    sections = re.split(r'^##\s+', text, flags=re.M)[1:]
    if not sections:
        raise ValueError('未找到试卷分节标题')
    legacy = any(re.match(r'^[一二三四五六七八九十]+、\s*（本题', s) for s in sections)
    entries = []
    expected = 1
    for section in sections:
        title, _, body = section.partition('\n')
        if legacy and '选择题' not in title and '填空题' not in title:
            entries.append((f'原卷{title.split("、")[0]}', body.strip()))
            continue
        markers = []
        next_number = 1 if legacy else expected
        for match in QUESTION.finditer(body):
            number = int(match.group(1) or match.group(2))
            if number == next_number:
                markers.append(match)
                next_number += 1
        if not markers:
            raise ValueError(f'本节未识别到题目：{title}')
        for i, match in enumerate(markers):
            number = int(match.group(1) or match.group(2))
            end = markers[i+1].start() if i+1 < len(markers) else len(body)
            label = f'原卷{title.split("、")[0]}（{number}）' if legacy else ''
            entries.append((label, body[match.end():end].strip()))
        if not legacy:
            expected = next_number
    return entries

def parse_year(path):
    return [(i+1, body.splitlines()) for i, (_, body) in enumerate(questions_from_text(Path(path).read_text(encoding='utf-8-sig')))]

def inline(text):
    parts = re.split(r'(\$\$.*?\$\$|\$[^$]*\$)', text, flags=re.S)
    for i in range(0, len(parts), 2):
        p = parts[i].replace('&emsp;', r'\hspace{1.5em}')
        p = re.sub(r'(?<!\\)_{3,}', lambda m: r'\underline{\hspace{20mm}}', p)
        p = re.sub(r'(?<!\\)([%&#_])', r'\\\1', p)
        parts[i] = p
    for i in range(1, len(parts), 2):
        parts[i] = parts[i].replace('（', '(').replace('）', ')')
    return re.sub(r'\*\*(.*?)\*\*', r'\\textbf{\1}', ''.join(parts), flags=re.S)

def question_tex(body):
    body = re.sub(r'^>.*$', '', body, flags=re.M)
    body = re.sub(r'(?m)^[ \t]*(!\[[^\]]*\]\([^)]+\))[ \t]*$', r'\n\n\1\n\n', body)
    body = re.sub(r'(?m)^\s*---\s*$', '', body)
    # Each option and each numbered subquestion begins a paragraph.
    body = re.sub(r'(?m)^\s*([（(][A-Da-d一二三四ⅠⅡⅢⅰⅱⅲ1-9][)）])', r'\n\1', body)
    body = re.sub(r'\s*&emsp;\s*(?=[（(][A-Da-d][)）])', '\n\n', body)
    pieces = []
    for para in re.split(r'\n\s*\n', body.strip()):
        para = para.strip()
        if not para:
            continue
        image = re.fullmatch(r'!\[([^\]]*)\]\(([^)]+)\)', para)
        if image:
            path = image.group(2).replace('\\', '/')
            if not path.startswith('_题图/') or '..' in Path(path).parts:
                raise ValueError('题图必须位于仓库 _题图 目录')
            size = r'width=.9\textwidth,height=75mm' if '选项' in image.group(1) else r'width=.62\textwidth,height=65mm'
            pieces.append(r'\begin{center}\includegraphics[' + size + r',keepaspectratio]{' + path + r'}\end{center}')
        else:
            pieces.append(inline(para))
    return '\n\n'.join(pieces)

def build_latex(year, entries):
    body = []
    for i, (label, content) in enumerate(entries, 1):
        heading = r'{\large\bfseries ' + str(year) + '.' + str(i) + '}'
        if label:
            heading += r'\quad {\small ' + label + '}'
        body.append(heading + '\n\n' + question_tex(content) + '\n\n\\vfill')
    return PREAMBLE + '\n\\newpage\n'.join(body) + '\n\\end{document}\n'

def make(year, source_dir=None, output_dir=None):
    source_dir = Path(source_dir) if source_dir else HERE.parent
    output_dir = Path(output_dir) if output_dir else HERE
    output_dir.mkdir(parents=True, exist_ok=True)
    source = source_dir / f'{year}年考研数学二试题.md'
    entries = questions_from_text(source.read_text(encoding='utf-8-sig'))
    tex = output_dir / f'{year}.tex'
    tex.write_text(build_latex(year, entries), encoding='utf-8')
    # Relative image names are resolved from the repository root.
    import os
    env = os.environ.copy()
    env['TEXINPUTS'] = str(source_dir).replace('\\','/') + '//' + os.pathsep + env.get('TEXINPUTS','')
    result = subprocess.run([XELATEX, '-no-shell-escape', '-halt-on-error', '-interaction=nonstopmode', tex.name], cwd=output_dir, env=env, capture_output=True, encoding='utf-8', errors='replace')
    log_path = output_dir / f'{year}.log'
    log = log_path.read_text(encoding='utf-8',errors='replace') if log_path.exists() else result.stdout
    errors = re.findall(r'(?:Missing character:|Overfull [^\n]*|! ).*', log)
    if result.returncode or errors:
        raise RuntimeError(f'{year} 排版检查失败\n' + '\n'.join(errors) + '\n' + result.stdout[-1800:])
    match = re.search(r'Output written on .*?\((\d+) pages?', result.stdout)
    if not match or int(match.group(1)) != len(entries):
        raise RuntimeError(f'{year} 页数不等于题数，应为 {len(entries)} 页')
    print(f'{year}: {len(entries)} questions, {len(entries)} pages, OK')
    return len(entries), True

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser()
    parser.add_argument('years', nargs='+', type=int)
    parser.add_argument('--source-dir', type=Path)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    for year in args.years:
        make(year, args.source_dir, args.output_dir)
