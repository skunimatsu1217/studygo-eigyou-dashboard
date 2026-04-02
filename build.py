#!/usr/bin/env python3
"""
StudyGO 営業 ドキュメントダッシュボード ビルドスクリプト

studygo eigyou フォルダをスキャンし、全ファイルを検出・分類して
ダッシュボードHTMLを自動生成する。

使い方:
  python build.py                    # HTMLを生成
  python build.py --push             # 生成後にgit push
  python build.py --watch            # フォルダ監視モード（変更検出で自動再生成）
  python build.py --watch --push     # 監視＋自動push
"""

import os
import sys
import json
import time
import hashlib
import subprocess
import re
from pathlib import Path
from datetime import datetime

# === 設定 ===
TARGET_DIR = Path(r"C:\Users\s_kun\OneDrive\デスクトップ\studygo eigyou")
DASHBOARD_DIR = Path(r"C:\Users\s_kun\OneDrive\デスクトップ\studygo-eigyou-dashboard")
OUTPUT_HTML = DASHBOARD_DIR / "index.html"

# === 対象拡張子 ===
TARGET_EXTENSIONS = {'.html', '.gs', '.js', '.py', '.txt', '.csv', '.xlsx', '.pptx', '.pdf'}

# === 除外条件 ===
SKIP_DIRS = {'node_modules', '.git', '__pycache__', '.claude', '.next', '.vercel',
             'output', 'output_tsv', 'images', '新しいフォルダー', 'my-team-task'}

SKIP_FILES = {'nul', 'requirements.txt'}


# === カテゴリ分類ルール ===
def classify_file(filename, rel_path):
    """ファイル名とパスからカテゴリとメタ情報を推定"""
    fn = filename.lower()
    rp = rel_path.lower()

    # _で始まるファイル（作業用）はスキップ
    if filename.startswith('_'):
        return None

    # ダッシュボード自身はスキップ
    if 'ダッシュボード' in filename:
        return None

    # 除外ファイル
    if filename in SKIP_FILES:
        return None

    # 画像ファイルはスキップ
    ext = os.path.splitext(filename)[1].lower()
    if ext in {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.ico'}:
        return None

    # JSONファイルはスキップ
    if ext == '.json':
        return None

    # 対象拡張子チェック
    if ext not in TARGET_EXTENSIONS:
        return None

    # manual/ サブフォルダ内は除外（別リポジトリで管理）
    if rp.startswith('manual/'):
        return None

    # reservation-system/ は除外（別プロジェクト）
    if rp.startswith('reservation-system/'):
        return None

    # X/ サブフォルダ内は除外
    if rp.startswith('x/'):
        return None

    # カテゴリ判定
    cat = 'other'
    doc_type = 'その他'
    icon = '📁'
    badge_class = 'dtype-other'

    if ext == '.gs':
        cat = 'gas'
        doc_type = 'GASシステム'
        icon = '⚙'
        badge_class = 'dtype-gas'
        if 'xbot' in fn or 'x_bot' in fn or 'x投稿' in fn:
            doc_type = 'X Bot'
        elif '営業管理' in fn:
            doc_type = '営業管理'
        elif 'メール' in fn or '契約通知' in fn:
            doc_type = 'メール系'
        elif 'ロッカー' in fn:
            doc_type = 'ロッカー管理'
        elif '在庫' in fn or '備品' in fn:
            doc_type = '在庫管理'
        elif 'クイズ' in fn:
            doc_type = 'クイズ'
        elif 'お知らせ' in fn or '周知' in fn:
            doc_type = 'お知らせ'
        elif '加盟法人' in fn:
            doc_type = '法人管理'
        elif '身分証' in fn:
            doc_type = '身分証'
        elif '月額' in fn:
            doc_type = '月額管理'
    elif ('セットアップ' in fn or '運用マニュアル' in fn or 'api取得ガイド' in fn
          or 'ガイド' in fn or 'マニュアル' in fn) and ext == '.txt':
        cat = 'guide'
        doc_type = 'ガイド'
        icon = '📗'
        badge_class = 'dtype-guide'
        if 'セットアップ' in fn:
            doc_type = 'セットアップガイド'
        elif '運用' in fn:
            doc_type = '運用マニュアル'
        elif 'api' in fn:
            doc_type = 'API取得ガイド'
    elif fn.startswith('x投稿_') or fn.startswith('x運用') or fn.startswith('x投稿スケジュール'):
        cat = 'x-content'
        doc_type = 'X投稿コンテンツ'
        icon = '🐦'
        badge_class = 'dtype-x'
        if '店舗紹介' in fn:
            doc_type = '店舗紹介投稿'
        elif '企画' in fn:
            doc_type = '企画シリーズ'
        elif '戦略' in fn or '運用' in fn or 'スケジュール' in fn:
            doc_type = 'X運用管理'
        elif 'コンテンツ変換' in fn:
            doc_type = '変換ツール'
            cat = 'script'
            icon = '🐍'
            badge_class = 'dtype-script'
    elif 'マーケティング' in fn or '分析' in fn:
        cat = 'data'
        doc_type = 'マーケティング分析'
        icon = '📊'
        badge_class = 'dtype-data'
    elif '席配置' in fn or 'スタジオマップ' in fn:
        cat = 'tool'
        doc_type = 'レイアウトツール'
        icon = '🗺'
        badge_class = 'dtype-tool'
    elif '手続きフロー' in fn:
        cat = 'tool'
        doc_type = '手続きフロー'
        icon = '📋'
        badge_class = 'dtype-tool'
    elif 'ロッカー' in fn and ext == '.html':
        cat = 'tool'
        doc_type = 'ロッカー管理'
        icon = '🔐'
        badge_class = 'dtype-tool'
    elif 'メールテンプレート' in fn:
        cat = 'tool'
        doc_type = 'メールツール'
        icon = '✉'
        badge_class = 'dtype-tool'
    elif 'instagram' in fn:
        cat = 'tool'
        doc_type = 'Instagram'
        icon = '📷'
        badge_class = 'dtype-tool'
    elif '身分証' in fn and ext == '.html':
        cat = 'tool'
        doc_type = '身分証ツール'
        icon = '🪪'
        badge_class = 'dtype-tool'
    elif '店舗検索' in fn:
        cat = 'tool'
        doc_type = '店舗検索サイト'
        icon = '🔍'
        badge_class = 'dtype-tool'
    elif '会員識別' in fn or '提案' in fn or '企画' in fn:
        cat = 'plan'
        doc_type = '提案書'
        icon = '📝'
        badge_class = 'dtype-plan'
    elif '架電' in fn or '営業リスト' in fn:
        cat = 'sales'
        doc_type = '営業リスト'
        icon = '📞'
        badge_class = 'dtype-sales'
    elif ext == '.csv' or ext == '.xlsx':
        cat = 'data'
        doc_type = 'データ'
        icon = '📊'
        badge_class = 'dtype-data'
        if 'チェックリスト' in fn:
            doc_type = 'チェックリスト'
        elif 'リスト' in fn:
            doc_type = 'リスト'
        elif '備品' in fn:
            doc_type = '備品データ'
    elif ext == '.py':
        cat = 'script'
        doc_type = 'スクリプト'
        icon = '🐍'
        badge_class = 'dtype-script'
        if 'scraper' in fn:
            doc_type = 'スクレイパー'
        elif 'quiz' in fn or 'クイズ' in fn:
            doc_type = 'クイズ'
        elif 'lstep' in fn or 'lステップ' in fn:
            doc_type = 'Lステップ'
    elif ext == '.js':
        cat = 'script'
        doc_type = 'JavaScript'
        icon = '📜'
        badge_class = 'dtype-script'
    elif ext == '.html':
        cat = 'tool'
        doc_type = 'HTMLツール'
        icon = '🌐'
        badge_class = 'dtype-tool'

    # 場所ラベル
    parts = rel_path.replace('\\', '/').split('/')
    if len(parts) > 1:
        location = parts[0] + '/'
    else:
        location = 'ルート'

    # タイトル整形
    title = os.path.splitext(filename)[0]
    title = re.sub(r'^20\d{6}_', '', title)  # 日付プレフィクス除去

    return {
        'id': hashlib.md5(rel_path.encode()).hexdigest()[:12],
        'title': title,
        'filename': filename,
        'rel_path': rel_path,
        'category': cat,
        'doc_type': doc_type,
        'icon': icon,
        'badge_class': badge_class,
        'location': location,
    }


def scan_folder():
    """TARGET_DIR以下の全ファイルをスキャン"""
    docs = []

    for root, dirs, files in os.walk(TARGET_DIR):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in sorted(files):
            full = Path(root) / f
            rel = str(full.relative_to(TARGET_DIR)).replace('\\', '/')
            info = classify_file(f, rel)
            if info:
                docs.append(info)

    return docs


# === 機能ステータスデータ（手動定義） ===
FEATURES = [
    # 完了・運用中
    {"name": "Webマニュアル（勉強カフェ向け）",
     "status": "complete", "status_label": "公開済み",
     "desc": "勉強カフェスタッフ向けスタディGO操作マニュアル。GitHub Pagesで公開中。",
     "tags": ["HTML/CSS", "GitHub Pages", "3ファイル構成"],
     "color": "green"},

    {"name": "メール一括送信システム",
     "status": "complete", "status_label": "運用中",
     "desc": "クレカ未登録ユーザーにアマギフキャンペーンメールを送信。GAS 947行。",
     "tags": ["GAS", "Gmail API", "スプレッドシート"],
     "color": "green"},

    {"name": "X Bot 自動投稿システム",
     "status": "complete", "status_label": "運用中",
     "desc": "X(Twitter)自動投稿（7:00/12:00/18:00/20:00の4件/日）。OAuth 1.0a、月間上限1,400件。",
     "tags": ["GAS", "X API", "OAuth 1.0a", "4件/日"],
     "color": "green"},

    {"name": "営業管理WEBシステム",
     "status": "complete", "status_label": "デプロイ済み",
     "desc": "営業活動の記録・追客アラート・データ検証。3ファイル構成（設定207行/バックエンド3,386行/フロントエンド2,654行）。",
     "tags": ["GAS", "Webアプリ", "3ファイル", "8フェーズ改善完了"],
     "color": "green",
     "progress": 100, "progress_text": "8/8 フェーズ完了"},

    {"name": "備品在庫管理システム",
     "status": "complete", "status_label": "運用中",
     "desc": "2スタジオの備品在庫数をWebアプリで送信→発注管理シートに自動反映。",
     "tags": ["GAS", "Webアプリ", "BP/新宿"],
     "color": "green"},

    {"name": "ロッカー管理システム",
     "status": "complete", "status_label": "完成",
     "desc": "2スタジオのロッカー空き状況を閲覧・管理。GAS Webアプリ＋スタンドアロンHTML。",
     "tags": ["GAS", "JSONP API", "タブレット最適化"],
     "color": "green"},

    {"name": "契約通知メール転送＋会員番号通知",
     "status": "complete", "status_label": "運用中",
     "desc": "契約通知メール受信→会員番号をお客様＋スタジオに自動送信。5分おきトリガー。",
     "tags": ["GAS", "Gmail API", "HTMLメール"],
     "color": "green"},

    {"name": "席配置プランナー",
     "status": "complete", "status_label": "完成",
     "desc": "新宿BPスタジオの席レイアウトをドラッグ&ドロップで設計。Canvas 2D。",
     "tags": ["HTML/Canvas", "localStorage", "ラウンジ2部屋"],
     "color": "green"},

    {"name": "手続きフロー一覧",
     "status": "complete", "status_label": "公開済み",
     "desc": "スタッフ向け5タブ構成の印刷可能A4フロー。GitHub Pagesで公開。",
     "tags": ["HTML", "PDF生成", "5タブ", "GitHub Pages"],
     "color": "green"},

    {"name": "クイズ管理システム",
     "status": "complete", "status_label": "完成",
     "desc": "スタディGO関連のクイズ管理。100問対応。",
     "tags": ["GAS", "JavaScript"],
     "color": "green"},

    {"name": "お知らせ管理システム",
     "status": "complete", "status_label": "完成",
     "desc": "アプリ内お知らせの管理・配信。",
     "tags": ["GAS"],
     "color": "green"},

    {"name": "X投稿コンテンツ（全シリーズ）",
     "status": "complete", "status_label": "作成済み",
     "desc": "店舗紹介313件、企画67件、坂道曲3,294件 他、多数のシリーズコンテンツ。",
     "tags": ["テキスト", "13シリーズ", "計5,000件超"],
     "color": "green"},

    {"name": "加盟法人自動登録",
     "status": "complete", "status_label": "完成",
     "desc": "加盟法人の自動登録処理。",
     "tags": ["GAS"],
     "color": "green"},

    {"name": "Lステップ自動応答",
     "status": "complete", "status_label": "完成",
     "desc": "LINE Lステップの自動応答シナリオ生成。",
     "tags": ["Python", "Excel出力"],
     "color": "green"},

    # 新規作成（最近のファイル）
    {"name": "周知管理システム",
     "status": "new", "status_label": "新規作成",
     "desc": "スタッフへの周知事項の管理・配信システム。",
     "tags": ["GAS", "2026-04-01"],
     "color": "cyan"},

    {"name": "Instagram投稿ツール",
     "status": "new", "status_label": "新規作成",
     "desc": "Instagram投稿のための画像・テキスト管理ツール。",
     "tags": ["HTML", "2026-04-01"],
     "color": "cyan"},

    {"name": "身分証写真アップロード/抽出",
     "status": "new", "status_label": "新規作成",
     "desc": "身分証写真のアップロード(GAS)と抽出(HTML)ツール。",
     "tags": ["GAS", "HTML", "2026-04-01"],
     "color": "cyan"},

    # 進行中
    {"name": "マーケティング戦略分析",
     "status": "in-progress", "status_label": "進行中",
     "desc": "市場データ/競合25+社/ユーザー傾向/学術エビデンス/PEST・3C・SWOT・STP分析完了。ペルソナ詳細・KPI設計等は未着手。",
     "tags": ["HTML", "競合分析", "フレームワーク分析"],
     "color": "yellow",
     "progress": 70, "progress_text": "主要分析完了・詳細未着手"},

    # 企画段階
    {"name": "スタディGO 店舗検索サイト",
     "status": "design", "status_label": "モック完成",
     "desc": "店舗検索サイトのモックアップ3パターン作成済み。",
     "tags": ["HTML", "モック", "3パターン"],
     "color": "pink"},

    {"name": "会員識別システム提案書",
     "status": "design", "status_label": "提案書完成",
     "desc": "会員識別システムの提案書を作成済み。",
     "tags": ["HTML", "提案書"],
     "color": "pink"},
]

CATEGORIES = {
    'complete': {'icon': '✅', 'title': '完了・運用中', 'color': 'green'},
    'new': {'icon': '🆕', 'title': '新規作成', 'color': 'cyan'},
    'in-progress': {'icon': '🔄', 'title': '進行中', 'color': 'yellow'},
    'design': {'icon': '📐', 'title': '設計・企画完了', 'color': 'pink'},
}

DOC_CATEGORIES = {
    'gas': {'icon': '⚙', 'title': 'GASシステム', 'badge': 'dtype-gas'},
    'tool': {'icon': '🛠', 'title': 'HTMLツール', 'badge': 'dtype-tool'},
    'guide': {'icon': '📗', 'title': 'ガイド・マニュアル', 'badge': 'dtype-guide'},
    'x-content': {'icon': '🐦', 'title': 'X投稿コンテンツ', 'badge': 'dtype-x'},
    'plan': {'icon': '📝', 'title': '企画書・提案書', 'badge': 'dtype-plan'},
    'sales': {'icon': '📞', 'title': '営業リスト', 'badge': 'dtype-sales'},
    'data': {'icon': '📊', 'title': 'データ・分析', 'badge': 'dtype-data'},
    'script': {'icon': '🐍', 'title': 'スクリプト', 'badge': 'dtype-script'},
    'other': {'icon': '📁', 'title': 'その他', 'badge': 'dtype-other'},
}


def generate_html(docs):
    """HTMLを生成"""
    # ドキュメント集計
    doc_counts = {}
    for d in docs:
        doc_counts[d['category']] = doc_counts.get(d['category'], 0) + 1
    total_docs = len(docs)

    # 機能集計
    feat_counts = {}
    for f in FEATURES:
        feat_counts[f['status']] = feat_counts.get(f['status'], 0) + 1
    total_features = len(FEATURES)

    # ドキュメントJSON（JS側で使用）
    docs_json = json.dumps(docs, ensure_ascii=False)

    html = f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>StudyGO 営業 ドキュメントダッシュボード</title>
<style>
:root {{
  --bg:#0f172a;--surface:#1e293b;--surface2:#334155;--border:#475569;
  --text:#f1f5f9;--text-sub:#94a3b8;--accent:#3b82f6;
  --green:#22c55e;--yellow:#eab308;--orange:#f97316;--red:#ef4444;
  --purple:#a855f7;--cyan:#06b6d4;--pink:#ec4899;
}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI','Hiragino Sans','Meiryo',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;line-height:1.6}}
.header{{background:linear-gradient(135deg,#1e3a5f,#0f172a);border-bottom:1px solid var(--border);padding:28px 40px 0}}
.header h1{{font-size:26px;font-weight:700}}.header h1 span{{color:var(--accent)}}
.header-meta{{display:flex;gap:24px;margin-top:6px;color:var(--text-sub);font-size:13px}}
.main-tabs{{display:flex;gap:0;margin-top:20px}}
.main-tab{{padding:10px 28px;font-size:14px;font-weight:600;color:var(--text-sub);background:transparent;border:1px solid transparent;border-bottom:none;border-radius:8px 8px 0 0;cursor:pointer;transition:.2s}}
.main-tab:hover{{color:var(--text)}}.main-tab.active{{background:var(--bg);color:var(--accent);border-color:var(--border)}}
.tab-count{{display:inline-block;background:var(--surface2);color:var(--text-sub);font-size:11px;font-weight:600;padding:1px 7px;border-radius:8px;margin-left:6px}}
.main-tab.active .tab-count{{background:rgba(59,130,246,.2);color:var(--accent)}}
.tab-content{{display:none}}.tab-content.active{{display:block}}
.stats-bar{{display:flex;gap:12px;padding:20px 40px;flex-wrap:wrap}}
.stat-card{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 20px;flex:1;min-width:110px;text-align:center}}
.stat-card .num{{font-size:28px;font-weight:700;line-height:1.2}}.stat-card .label{{font-size:11px;color:var(--text-sub);margin-top:2px}}
.filter-bar{{padding:0 40px 12px;display:flex;gap:6px;flex-wrap:wrap;align-items:center}}
.filter-btn{{background:var(--surface);border:1px solid var(--border);color:var(--text-sub);padding:5px 14px;border-radius:20px;font-size:12px;cursor:pointer;transition:.2s}}
.filter-btn:hover,.filter-btn.active{{background:var(--accent);color:#fff;border-color:var(--accent)}}
.legend{{padding:0 40px 14px;display:flex;gap:14px;flex-wrap:wrap;font-size:11px;color:var(--text-sub)}}
.legend-item{{display:flex;align-items:center;gap:5px}}.legend-dot{{width:9px;height:9px;border-radius:50%}}
.content{{padding:0 40px 40px}}
.category{{margin-bottom:28px}}
.category-header{{display:flex;align-items:center;gap:10px;margin-bottom:12px;padding-bottom:6px;border-bottom:1px solid var(--border)}}
.category-icon{{width:32px;height:32px;border-radius:7px;display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0}}
.category-title{{font-size:16px;font-weight:600}}
.category-count{{background:var(--surface2);color:var(--text-sub);font-size:11px;padding:2px 8px;border-radius:10px}}
.features-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(400px,1fr));gap:14px}}
.feature-card{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:18px;transition:.15s;position:relative;overflow:hidden}}
.feature-card:hover{{transform:translateY(-2px);box-shadow:0 6px 20px rgba(0,0,0,.3)}}
.feature-card .accent-bar{{position:absolute;top:0;left:0;width:4px;height:100%;border-radius:4px 0 0 4px}}
.card-top{{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;margin-bottom:6px}}
.feature-name{{font-size:15px;font-weight:600;line-height:1.4}}
.status-badge{{font-size:10px;font-weight:600;padding:2px 9px;border-radius:10px;white-space:nowrap;flex-shrink:0}}
.status-complete{{background:rgba(34,197,94,.15);color:var(--green)}}
.status-new{{background:rgba(6,182,212,.15);color:var(--cyan)}}
.status-in-progress{{background:rgba(234,179,8,.15);color:var(--yellow)}}
.status-design{{background:rgba(236,72,153,.15);color:var(--pink)}}
.feature-desc{{font-size:12px;color:var(--text-sub);margin-bottom:10px;line-height:1.5}}
.progress-row{{display:flex;align-items:center;gap:8px;margin-bottom:8px}}
.progress-bar{{flex:1;height:5px;background:var(--surface2);border-radius:3px;overflow:hidden}}
.progress-fill{{height:100%;border-radius:3px}}
.progress-text{{font-size:11px;color:var(--text-sub);white-space:nowrap}}
.tag-row{{display:flex;gap:5px;flex-wrap:wrap}}
.tag{{font-size:10px;padding:2px 7px;border-radius:5px;background:var(--surface2);color:var(--text-sub)}}
.blocker{{margin-top:8px;padding:7px 10px;background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.2);border-radius:6px;font-size:11px;color:var(--red)}}
.blocker-label{{font-weight:600;margin-right:4px}}

/* Doc tab */
.search-box{{background:var(--surface);border:1px solid var(--border);color:var(--text);padding:6px 14px;border-radius:20px;font-size:13px;width:280px;outline:none}}
.search-box::placeholder{{color:var(--text-sub)}}.search-box:focus{{border-color:var(--accent)}}
.doc-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(380px,1fr));gap:10px}}
.doc-card{{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:14px 16px;display:flex;gap:12px;align-items:flex-start;transition:.12s;position:relative}}
.doc-card:hover{{transform:translateY(-1px);box-shadow:0 4px 12px rgba(0,0,0,.25)}}
.doc-icon{{width:36px;height:36px;border-radius:8px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:16px}}
.doc-info{{flex:1;min-width:0}}.doc-title{{font-size:13px;font-weight:600;line-height:1.4;word-break:break-all}}
.doc-meta{{font-size:11px;color:var(--text-sub);margin-top:3px;display:flex;gap:10px;flex-wrap:wrap;align-items:center}}
.doc-type-badge{{font-size:10px;font-weight:600;padding:1px 7px;border-radius:8px;white-space:nowrap}}
.dtype-gas{{background:rgba(249,115,22,.15);color:var(--orange)}}
.dtype-tool{{background:rgba(6,182,212,.15);color:var(--cyan)}}
.dtype-guide{{background:rgba(34,197,94,.15);color:var(--green)}}
.dtype-x{{background:rgba(59,130,246,.15);color:var(--accent)}}
.dtype-plan{{background:rgba(236,72,153,.15);color:var(--pink)}}
.dtype-sales{{background:rgba(168,85,247,.15);color:var(--purple)}}
.dtype-data{{background:rgba(234,179,8,.15);color:var(--yellow)}}
.dtype-script{{background:rgba(6,182,212,.15);color:var(--cyan)}}
.dtype-other{{background:var(--surface2);color:var(--text-sub)}}
.dtype-review{{background:rgba(59,130,246,.15);color:var(--accent)}}
.doc-category-section{{margin-bottom:24px}}
.doc-category-header{{display:flex;align-items:center;gap:10px;margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid var(--border)}}

/* 必要/不要/保留 ボタン */
.triage-btns{{display:flex;gap:4px;margin-top:8px}}
.triage-btn{{font-size:10px;padding:3px 10px;border-radius:12px;border:1px solid var(--border);background:transparent;color:var(--text-sub);cursor:pointer;transition:.15s;font-weight:600}}
.triage-btn:hover{{opacity:.8}}
.triage-btn.sel-need{{background:rgba(34,197,94,.2);color:var(--green);border-color:var(--green)}}
.triage-btn.sel-skip{{background:rgba(239,68,68,.15);color:var(--red);border-color:var(--red)}}
.triage-btn.sel-hold{{background:rgba(234,179,8,.15);color:var(--yellow);border-color:var(--yellow)}}
.triage-btn.sel-done{{background:rgba(6,182,212,.2);color:var(--cyan);border-color:var(--cyan)}}

/* 必要/不要/保留 フィルタタブ */
.triage-tabs{{display:flex;gap:0;margin:0 40px 16px;border-bottom:2px solid var(--border)}}
.triage-tab{{padding:8px 24px;font-size:13px;font-weight:600;color:var(--text-sub);background:transparent;border:none;cursor:pointer;position:relative;transition:.2s}}
.triage-tab:hover{{color:var(--text)}}
.triage-tab.active{{color:var(--accent)}}
.triage-tab.active::after{{content:'';position:absolute;bottom:-2px;left:0;right:0;height:2px;background:var(--accent);border-radius:1px}}
.triage-tab .tc{{display:inline-block;background:var(--surface2);font-size:10px;padding:1px 6px;border-radius:8px;margin-left:5px}}
.triage-tab.active .tc{{background:rgba(59,130,246,.2);color:var(--accent)}}

.doc-card.hidden-triage{{display:none!important}}

@media(max-width:900px){{
  .features-grid,.doc-grid{{grid-template-columns:1fr}}
  .header,.stats-bar,.filter-bar,.content,.legend,.triage-tabs{{padding-left:16px;padding-right:16px}}
  .search-box{{width:100%}}
}}
</style>
</head>
<body>

<div class="header">
  <h1><span>StudyGO</span> 営業 ドキュメントダッシュボード</h1>
  <div class="header-meta">
    <span>作成者: 國松</span>
    <span>最終更新: {datetime.now().strftime("%Y年%m月%d日 %H:%M")}</span>
    <span>自動生成</span>
  </div>
  <div class="main-tabs">
    <button class="main-tab active" onclick="switchTab('features')">ステータス管理<span class="tab-count">{total_features}</span></button>
    <button class="main-tab" onclick="switchTab('docs')">ドキュメント一覧<span class="tab-count">{total_docs}</span></button>
  </div>
</div>

<!-- ===== TAB 1: ステータス管理 ===== -->
<div id="tab-features" class="tab-content active">
<div class="stats-bar">
'''

    # Feature stats
    color_map = {'complete': 'green', 'new': 'cyan', 'in-progress': 'yellow', 'design': 'pink'}
    label_map = {'complete': '完了・運用中', 'new': '新規作成', 'in-progress': '進行中', 'design': '設計・企画完了'}
    for st in ['complete', 'new', 'in-progress', 'design']:
        c = feat_counts.get(st, 0)
        html += f'  <div class="stat-card"><div class="num" style="color:var(--{color_map[st]})">{c}</div><div class="label">{label_map[st]}</div></div>\n'

    html += '</div>\n'

    # Feature triage tabs
    html += '''<div class="triage-tabs" id="feat-triage-tabs">
  <button class="triage-tab active" onclick="filterFeatTriage('all')">すべて<span class="tc" id="ftc-all">0</span></button>
  <button class="triage-tab" onclick="filterFeatTriage('need')">必要<span class="tc" id="ftc-need">0</span></button>
  <button class="triage-tab" onclick="filterFeatTriage('hold')">保留<span class="tc" id="ftc-hold">0</span></button>
  <button class="triage-tab" onclick="filterFeatTriage('skip')">不要<span class="tc" id="ftc-skip">0</span></button>
  <button class="triage-tab" onclick="filterFeatTriage('done')">実施済み<span class="tc" id="ftc-done">0</span></button>
  <button class="triage-tab" onclick="filterFeatTriage('unset')">未分類<span class="tc" id="ftc-unset">0</span></button>
</div>
'''

    # Legend
    html += '<div class="legend">\n'
    for st in ['complete', 'new', 'in-progress', 'design']:
        html += f'  <div class="legend-item"><div class="legend-dot" style="background:var(--{color_map[st]})"></div>{label_map[st]}</div>\n'
    html += '</div>\n'

    # Filter buttons
    html += '<div class="filter-bar">\n'
    html += f'  <button class="filter-btn active" onclick="filterFeatures(\'all\')">すべて ({total_features})</button>\n'
    for st in ['complete', 'new', 'in-progress', 'design']:
        html += f'  <button class="filter-btn" onclick="filterFeatures(\'{st}\')">{label_map[st]}</button>\n'
    html += '</div>\n'

    html += '<div class="content">\n'

    # Feature categories
    for st_key, cat_info in CATEGORIES.items():
        feats_in_cat = [f for f in FEATURES if f['status'] == st_key]
        if not feats_in_cat:
            continue
        html += f'<div class="category" data-category="{st_key}">\n'
        html += f'  <div class="category-header"><div class="category-icon" style="background:rgba(var(--{cat_info["color"]}),0.15)">{cat_info["icon"]}</div>'
        html += f'<div class="category-title">{cat_info["title"]}</div><span class="category-count">{len(feats_in_cat)}件</span></div>\n'
        html += '  <div class="features-grid">\n'

        for f in feats_in_cat:
            sc = f.get('status_class', f'status-{f["status"]}')
            feat_id = 'feat_' + hashlib.md5(f['name'].encode()).hexdigest()[:10]
            html += f'    <div class="feature-card" data-status="{f["status"]}" data-feat-id="{feat_id}">\n'
            html += f'      <div class="accent-bar" style="background:var(--{f["color"]})"></div>\n'
            html += f'      <div class="card-top"><div class="feature-name">{f["name"]}</div><span class="status-badge {sc}">{f["status_label"]}</span></div>\n'
            html += f'      <div class="feature-desc">{f["desc"]}</div>\n'
            if 'progress' in f:
                html += f'      <div class="progress-row"><div class="progress-bar"><div class="progress-fill" style="width:{f["progress"]}%;background:var(--{f["color"]})"></div></div><span class="progress-text">{f["progress_text"]}</span></div>\n'
            if 'extra_html' in f:
                html += f'      {f["extra_html"]}\n'
            html += '      <div class="tag-row">' + ''.join(f'<span class="tag">{t}</span>' for t in f['tags']) + '</div>\n'
            if 'blocker' in f:
                html += f'      <div class="blocker"><span class="blocker-label">ブロッカー:</span>{f["blocker"]}</div>\n'
            html += f'      <div class="triage-btns"><button class="triage-btn" data-val="need" onclick="setFeatTriage(\'{feat_id}\',\'need\',this)">必要</button><button class="triage-btn" data-val="hold" onclick="setFeatTriage(\'{feat_id}\',\'hold\',this)">保留</button><button class="triage-btn" data-val="skip" onclick="setFeatTriage(\'{feat_id}\',\'skip\',this)">不要</button><button class="triage-btn" data-val="done" onclick="setFeatTriage(\'{feat_id}\',\'done\',this)">実施済み</button></div>\n'
            html += '    </div>\n'

        html += '  </div>\n</div>\n'

    html += '</div>\n</div>\n'

    # === TAB 2: Documents ===
    html += '<div id="tab-docs" class="tab-content">\n'

    # Doc stats
    html += '<div class="stats-bar">\n'
    doc_cat_colors = {'gas': 'orange', 'tool': 'cyan', 'guide': 'green', 'x-content': 'accent',
                      'plan': 'pink', 'sales': 'purple', 'data': 'yellow', 'script': 'cyan', 'other': 'text-sub'}
    for cat_key, cat_info in DOC_CATEGORIES.items():
        c = doc_counts.get(cat_key, 0)
        col = doc_cat_colors.get(cat_key, 'text-sub')
        html += f'  <div class="stat-card"><div class="num" style="color:var(--{col})">{c}</div><div class="label">{cat_info["title"]}</div></div>\n'
    html += '</div>\n'

    # Triage tabs
    html += '''<div class="triage-tabs">
  <button class="triage-tab active" onclick="filterTriage('all')">すべて<span class="tc" id="tc-all">0</span></button>
  <button class="triage-tab" onclick="filterTriage('need')">必要<span class="tc" id="tc-need">0</span></button>
  <button class="triage-tab" onclick="filterTriage('hold')">保留<span class="tc" id="tc-hold">0</span></button>
  <button class="triage-tab" onclick="filterTriage('skip')">不要<span class="tc" id="tc-skip">0</span></button>
  <button class="triage-tab" onclick="filterTriage('done')">実施済み<span class="tc" id="tc-done">0</span></button>
  <button class="triage-tab" onclick="filterTriage('unset')">未分類<span class="tc" id="tc-unset">0</span></button>
</div>
'''

    # Filter bar
    html += '<div class="filter-bar">\n'
    html += '  <input type="text" class="search-box" id="docSearch" placeholder="ドキュメント名で検索..." oninput="applyDocFilters()">\n'
    html += '  <button class="filter-btn active" data-doc-filter="all" onclick="filterDocType(\'all\')">すべて</button>\n'
    for cat_key, cat_info in DOC_CATEGORIES.items():
        html += f'  <button class="filter-btn" data-doc-filter="{cat_key}" onclick="filterDocType(\'{cat_key}\')">{cat_info["title"]}</button>\n'
    html += '</div>\n'

    html += '<div class="content" id="doc-content">\n'

    # Doc category sections
    for cat_key, cat_info in DOC_CATEGORIES.items():
        cat_docs = [d for d in docs if d['category'] == cat_key]
        if not cat_docs:
            continue
        html += f'<div class="doc-category-section" data-doc-cat="{cat_key}">\n'
        html += f'  <div class="doc-category-header"><div class="category-icon">{cat_info["icon"]}</div>'
        html += f'<div class="category-title">{cat_info["title"]}</div><span class="category-count">{len(cat_docs)}件</span></div>\n'
        html += '  <div class="doc-grid">\n'

        for d in cat_docs:
            html += f'    <div class="doc-card" data-dtype="{d["category"]}" data-doc-id="{d["id"]}">'
            html += f'<div class="doc-icon">{d["icon"]}</div>'
            html += f'<div class="doc-info"><div class="doc-title">{d["title"]}</div>'
            html += f'<div class="doc-meta"><span class="doc-type-badge {d["badge_class"]}">{d["doc_type"]}</span><span>{d["location"]}</span></div>'
            html += f'<div class="triage-btns">'
            html += f'<button class="triage-btn" data-val="need" onclick="setTriage(\'{d["id"]}\',\'need\',this)">必要</button>'
            html += f'<button class="triage-btn" data-val="hold" onclick="setTriage(\'{d["id"]}\',\'hold\',this)">保留</button>'
            html += f'<button class="triage-btn" data-val="skip" onclick="setTriage(\'{d["id"]}\',\'skip\',this)">不要</button>'
            html += f'<button class="triage-btn" data-val="done" onclick="setTriage(\'{d["id"]}\',\'done\',this)">実施済み</button>'
            html += f'</div>'
            html += f'</div></div>\n'

        html += '  </div>\n</div>\n'

    html += '</div>\n</div>\n'

    # Features JSON for JS
    feats_list = []
    for f in FEATURES:
        fid = 'feat_' + hashlib.md5(f['name'].encode()).hexdigest()[:10]
        feats_list.append({'id': fid, 'name': f['name']})
    feats_json = json.dumps(feats_list, ensure_ascii=False)

    # === JavaScript ===
    html += f'''
<script>
const DOCS_DATA = {docs_json};
const FEATS_DATA = {feats_json};

// === Tab switching ===
function switchTab(tab) {{
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.main-tab').forEach(t => t.classList.remove('active'));
  document.getElementById('tab-' + tab).classList.add('active');
  event.target.closest('.main-tab').classList.add('active');
}}

// === Triage state (shared localStorage) ===
let triageState = {{}};
try {{ triageState = JSON.parse(localStorage.getItem('studygo_eigyou_triage') || '{{}}'); }} catch(e) {{}}

function saveTriage() {{
  localStorage.setItem('studygo_eigyou_triage', JSON.stringify(triageState));
  updateTriageCounts();
  updateFeatTriageCounts();
  applyDocFilters();
  applyFeatTriageFilter();
}}

// === Generic triage set ===
function setTriageGeneric(id, val, btn) {{
  if (triageState[id] === val) {{
    delete triageState[id];
    btn.classList.remove('sel-need','sel-skip','sel-hold','sel-done');
  }} else {{
    triageState[id] = val;
    const row = btn.parentElement;
    row.querySelectorAll('.triage-btn').forEach(b => b.classList.remove('sel-need','sel-skip','sel-hold','sel-done'));
    btn.classList.add('sel-' + val);
  }}
  saveTriage();
}}
function setTriage(docId, val, btn) {{ setTriageGeneric(docId, val, btn); }}
function setFeatTriage(featId, val, btn) {{ setTriageGeneric(featId, val, btn); }}

// ====== FEATURE TAB ======

let activeFeatStatus = 'all';
function filterFeatures(status) {{
  activeFeatStatus = status;
  document.querySelectorAll('#tab-features .filter-btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  applyFeatTriageFilter();
}}

let activeFeatTriage = 'all';
function filterFeatTriage(val) {{
  activeFeatTriage = val;
  document.querySelectorAll('#feat-triage-tabs .triage-tab').forEach(t => t.classList.remove('active'));
  event.target.closest('.triage-tab').classList.add('active');
  applyFeatTriageFilter();
}}

function applyFeatTriageFilter() {{
  document.querySelectorAll('#tab-features .category').forEach(cat => {{
    let visCount = 0;
    cat.querySelectorAll('.feature-card').forEach(card => {{
      const st = card.dataset.status;
      const fid = card.dataset.featId;
      const triage = triageState[fid] || 'unset';
      let show = true;
      if (activeFeatStatus !== 'all' && st !== activeFeatStatus) show = false;
      if (activeFeatTriage !== 'all' && triage !== activeFeatTriage) show = false;
      card.style.display = show ? '' : 'none';
      if (show) visCount++;
    }});
    cat.style.display = visCount > 0 ? '' : 'none';
  }});
}}

function updateFeatTriageCounts() {{
  let counts = {{all: FEATS_DATA.length, need:0, skip:0, hold:0, done:0, unset:0}};
  FEATS_DATA.forEach(f => {{
    const v = triageState[f.id];
    if (v === 'need') counts.need++;
    else if (v === 'skip') counts.skip++;
    else if (v === 'hold') counts.hold++;
    else if (v === 'done') counts.done++;
    else counts.unset++;
  }});
  for (const k of ['all','need','skip','hold','done','unset']) {{
    const el = document.getElementById('ftc-' + k);
    if (el) el.textContent = counts[k];
  }}
}}

// ====== DOC TAB ======

function updateTriageCounts() {{
  let counts = {{all: DOCS_DATA.length, need:0, skip:0, hold:0, done:0, unset:0}};
  DOCS_DATA.forEach(d => {{
    const v = triageState[d.id];
    if (v === 'need') counts.need++;
    else if (v === 'skip') counts.skip++;
    else if (v === 'hold') counts.hold++;
    else if (v === 'done') counts.done++;
    else counts.unset++;
  }});
  for (const k of ['all','need','skip','hold','done','unset']) {{
    const el = document.getElementById('tc-' + k);
    if (el) el.textContent = counts[k];
  }}
}}

let activeTriageFilter = 'all';
function filterTriage(val) {{
  activeTriageFilter = val;
  document.querySelectorAll('#tab-docs .triage-tabs .triage-tab').forEach(t => t.classList.remove('active'));
  event.target.closest('.triage-tab').classList.add('active');
  applyDocFilters();
}}

let activeDocType = 'all';
function filterDocType(dtype) {{
  activeDocType = dtype;
  document.querySelectorAll('#tab-docs .filter-bar .filter-btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  applyDocFilters();
}}

function applyDocFilters() {{
  const q = (document.getElementById('docSearch')?.value || '').toLowerCase();
  document.querySelectorAll('.doc-category-section').forEach(sec => {{
    if (activeDocType !== 'all' && sec.dataset.docCat !== activeDocType) {{
      sec.style.display = 'none'; return;
    }}
    let visCount = 0;
    sec.querySelectorAll('.doc-card').forEach(card => {{
      const title = card.querySelector('.doc-title').textContent.toLowerCase();
      const dtype = card.dataset.dtype;
      const docId = card.dataset.docId;
      const triage = triageState[docId] || 'unset';
      let show = true;
      if (activeDocType !== 'all' && dtype !== activeDocType) show = false;
      if (q && !title.includes(q)) show = false;
      if (activeTriageFilter !== 'all' && triage !== activeTriageFilter) show = false;
      card.style.display = show ? '' : 'none';
      if (show) visCount++;
    }});
    sec.style.display = visCount > 0 ? '' : 'none';
  }});
}}

// === Init ===
function initTriage() {{
  document.querySelectorAll('.doc-card').forEach(card => {{
    const docId = card.dataset.docId;
    const val = triageState[docId];
    if (val) {{
      const btn = card.querySelector(`.triage-btn[data-val="${{val}}"]`);
      if (btn) btn.classList.add('sel-' + val);
    }}
  }});
  document.querySelectorAll('.feature-card').forEach(card => {{
    const fid = card.dataset.featId;
    if (!fid) return;
    const val = triageState[fid];
    if (val) {{
      const btn = card.querySelector(`.triage-btn[data-val="${{val}}"]`);
      if (btn) btn.classList.add('sel-' + val);
    }}
  }});
  updateTriageCounts();
  updateFeatTriageCounts();
}}
document.addEventListener('DOMContentLoaded', initTriage);
</script>
</body>
</html>'''

    return html


def build():
    print("Scanning folder...")
    docs = scan_folder()
    print(f"  Found {len(docs)} documents")

    print("Generating HTML...")
    html = generate_html(docs)
    OUTPUT_HTML.write_text(html, encoding='utf-8')
    print(f"  Written to {OUTPUT_HTML}")

    return docs


def git_push():
    os.chdir(DASHBOARD_DIR)
    subprocess.run(["git", "add", "index.html"], check=True)
    result = subprocess.run(["git", "diff", "--cached", "--quiet"])
    if result.returncode == 0:
        print("  No changes to commit")
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    subprocess.run(["git", "commit", "-m", f"auto-update: {now}"], check=True)
    subprocess.run(["git", "push"], check=True)
    print("  Pushed to GitHub")


def watch(do_push=False):
    """フォルダ監視モード"""
    print("Watch mode started. Ctrl+C to stop.")
    print(f"  Monitoring: {TARGET_DIR}")
    last_hash = ""

    while True:
        files = []
        for root, dirs, fnames in os.walk(TARGET_DIR):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in fnames:
                ext = os.path.splitext(f)[1].lower()
                if ext in TARGET_EXTENSIONS and not f.startswith('_') and 'ダッシュボード' not in f:
                    full = os.path.join(root, f)
                    mtime = os.path.getmtime(full)
                    files.append(f"{full}:{mtime}")

        current_hash = hashlib.md5("\n".join(sorted(files)).encode()).hexdigest()

        if current_hash != last_hash and last_hash != "":
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Change detected! Rebuilding...")
            build()
            if do_push:
                git_push()
            print("Done. Watching...")

        last_hash = current_hash
        time.sleep(5)


if __name__ == '__main__':
    do_push = '--push' in sys.argv
    do_watch = '--watch' in sys.argv

    build()

    if do_push:
        git_push()

    if do_watch:
        watch(do_push)
    else:
        print("\nDone! Run with --watch for auto-update mode.")
