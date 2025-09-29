#!/usr/bin/env python3
# scripts/update.py
import os, sys, yaml, requests, hashlib, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPS_YAML = ROOT / 'apps.yaml'
DOCS_INDEX = ROOT / 'docs' / 'index.html'

HEADERS = {'Accept': 'application/vnd.github+json'}
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN') or os.environ.get('INPUT_GITHUB_TOKEN')
if GITHUB_TOKEN:
    HEADERS['Authorization'] = f'token {GITHUB_TOKEN}'

def load_apps():
    with open(APPS_YAML, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    return data.get('apps', [])

def pick_asset(assets, prefer_contains=None):
    if not assets:
        return None
    if prefer_contains:
        for a in assets:
            if prefer_contains.lower() in a.get('name','').lower():
                return a
    return assets[0]

def compute_sha256_from_url(url, max_bytes=200*1024*1024):
    resp = requests.get(url, stream=True, timeout=30)
    resp.raise_for_status()
    total = 0
    h = hashlib.sha256()
    with tempfile.NamedTemporaryFile(delete=True) as tmp:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                total += len(chunk)
                if total > max_bytes:
                    raise RuntimeError("Arquivo maior que limite para checksum")
                tmp.write(chunk)
                h.update(chunk)
    return h.hexdigest()

def get_release_info(github_repo):
    api = f'https://api.github.com/repos/{github_repo}/releases/latest'
    r = requests.get(api, headers=HEADERS, timeout=20)
    if r.status_code != 200:
        return None
    return r.json()

def make_card_html(app, version, download_url, checksum):
    nome = app.get('nome','')
    descricao = app.get('descricao','')
    sistema = app.get('sistema','')
    initial = ''.join([p[0] for p in nome.split()])[:2].upper()
    checksum_html = f'<div class="card-meta"><small>SHA-256: <code>{checksum}</code></small></div>' if checksum else ''
    card = (
        '<div class="card">
'
        f'  <div class="icon">{initial}</div>
'
        '  <div class="card-body">
'
        f'    <div class="card-title">{nome}</div>
'
        f'    <div class="card-desc">{descricao}</div>
'
        '    <div class="card-meta">
'
        f'      <div class="tag">{sistema}</div>
'
        '      <div style="flex:1"></div>
'
        f'      <a class="btn" href="{download_url}" target="_blank" rel="noopener">Download oficial</a>
'
        '    </div>
'
        f'    {checksum_html}
'
        '  </div>
'
        '</div>
'
    )
    return card

def main():
    apps = load_apps()
    cards = []
    for app in apps:
        nome = app.get('nome')
        version = None
        download_url = app.get('url_oficial') or '#'
        checksum = None
        github_repo = app.get('github_repo')
        try:
            if github_repo:
                rel = get_release_info(github_repo)
                if rel:
                    version = rel.get('tag_name') or rel.get('name')
                    assets = rel.get('assets', [])
                    asset = pick_asset(assets)
                    if asset:
                        download_url = asset.get('browser_download_url') or download_url
                    else:
                        download_url = rel.get('html_url') or download_url
            if app.get('compute_checksum'):
                try:
                    checksum = compute_sha256_from_url(download_url)
                except Exception as e:
                    checksum = f'Erro: {e}'
        except Exception as e:
            print(f'Erro ao processar {nome}: {e}', file=sys.stderr)
        cards.append(make_card_html(app, version, download_url, checksum))
        time.sleep(0.5)

    html = DOCS_INDEX.read_text(encoding='utf-8')
    start_marker = '<!-- APPS_CARDS -->'
    end_marker = '<!-- /APPS_CARDS -->'
    if start_marker in html and end_marker in html:
        before = html.split(start_marker)[0] + start_marker + '
'
        after = '
' + end_marker + html.split(end_marker)[1]
        new_section = '<div class="cards-grid">
' + '
'.join(cards) + '
</div>'
        new_html = before + new_section + after
        if new_html != html:
            DOCS_INDEX.write_text(new_html, encoding='utf-8')
            print('docs/index.html atualizado.')
        else:
            print('Sem mudanças.')
    else:
        print('Marcadores não encontrados em docs/index.html', file=sys.stderr)

if __name__ == '__main__':
    main()
