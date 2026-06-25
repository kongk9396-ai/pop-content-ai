"""
팝성형외과 블로그 대시보드
실행: python dashboard.py
브라우저: http://localhost:5000
"""

from flask import Flask, render_template_string, jsonify, request
from pathlib import Path
from datetime import datetime
import os
import json
from dotenv import load_dotenv

load_dotenv()  # .env 파일 자동 로드

app = Flask(__name__)
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
PUBLISHED_FILE = BASE_DIR / "published.json"

def load_published():
    if PUBLISHED_FILE.exists():
        return json.loads(PUBLISHED_FILE.read_text(encoding="utf-8"))
    return {}

def save_published(data):
    PUBLISHED_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def get_posts(date_str):
    folder = OUTPUT_DIR / date_str
    if not folder.exists():
        return []
    published = load_published()
    posts = []
    seen = set()  # 중복 방지

    # 루트 + completed + failed 전부 스캔
    scan_dirs = [
        (folder, False),
        (folder / "completed", True),
        (folder / "failed", False),
    ]

    for scan_dir, is_completed in scan_dirs:
        if not scan_dir.exists():
            continue
        for f in sorted(scan_dir.glob("*.txt")):
            post_id = f"{date_str}_{f.name}"
            if post_id in seen:
                continue
            seen.add(post_id)

            content = f.read_text(encoding="utf-8")
            info = {
                "filename": f.name,
                "date": date_str,
                "content": content,
                "completed": is_completed,
                "post_id": post_id,
            }
            for line in content.split("\n")[:12]:
                if line.startswith("카테고리:"): info["category"] = line.replace("카테고리:","").strip()
                elif line.startswith("키워드:"): info["keyword"] = line.replace("키워드:","").strip()
                elif line.startswith("제목:"): info["title"] = line.replace("제목:","").strip()
            info["published"] = published.get(post_id, is_completed)
            posts.append(info)
    return posts

def get_available_dates():
    if not OUTPUT_DIR.exists():
        return []
    return sorted([d.name for d in OUTPUT_DIR.iterdir() if d.is_dir() and d.name.isdigit()], reverse=True)[:30]

def get_used_keywords():
    """발행완료된 키워드만 사용이력으로 반환"""
    published = load_published()
    used = {"eye": [], "lifting": [], "nose": []}
    cat_map = {"눈성형": "eye", "리프팅": "lifting", "코성형": "nose"}
    if not OUTPUT_DIR.exists():
        return used
    for date_folder in sorted(OUTPUT_DIR.iterdir(), reverse=True):
        if not date_folder.is_dir() or not date_folder.name.isdigit():
            continue
        scan_dirs = [date_folder, date_folder / "completed", date_folder / "failed"]
        seen_files = set()
        for scan_dir in scan_dirs:
            if not scan_dir.exists():
                continue
            for f in scan_dir.glob("*.txt"):
                if f.name in seen_files:
                    continue
                seen_files.add(f.name)
                post_id = f"{date_folder.name}_{f.name}"
                if not published.get(post_id):
                    continue
                content = f.read_text(encoding="utf-8")
                cat = kw = ""
                for line in content.split("\n")[:10]:
                    if line.startswith("카테고리:"): cat = line.replace("카테고리:","").strip()
                    elif line.startswith("키워드:"): kw = line.replace("키워드:","").strip()
                if cat in cat_map and kw:
                    used[cat_map[cat]].append({"keyword": kw, "date": date_folder.name})
    return used

HTML = r"""
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>팝성형외과 블로그 대시보드</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:'Segoe UI',sans-serif; background:#f0f2f5; color:#333; }
.header { background:linear-gradient(135deg,#1a1a2e,#16213e); color:white; padding:20px 30px; display:flex; justify-content:space-between; align-items:center; }
.header h1 { font-size:20px; font-weight:600; }
.header .date { font-size:13px; color:#aaa; }
.container { max-width:1200px; margin:0 auto; padding:24px; }
.stats-row { display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-bottom:24px; }
.stat-card { background:white; border-radius:12px; padding:20px; box-shadow:0 2px 8px rgba(0,0,0,0.06); }
.stat-card .label { font-size:12px; color:#888; margin-bottom:8px; }
.stat-card .value { font-size:28px; font-weight:700; color:#1a1a2e; }
.stat-card .sub { font-size:12px; color:#aaa; margin-top:4px; }
.progress-bar { height:6px; background:#eee; border-radius:3px; margin-top:10px; overflow:hidden; }
.progress-bar .fill { height:100%; border-radius:3px; }
.fill-eye{background:#4f8ef7;} .fill-lifting{background:#f7934f;} .fill-nose{background:#4fd19e;} .fill-total{background:#7c5fe6;}
.section { background:white; border-radius:12px; padding:20px; box-shadow:0 2px 8px rgba(0,0,0,0.06); margin-bottom:20px; }
.section h2 { font-size:15px; font-weight:600; margin-bottom:16px; color:#1a1a2e; }
.top-bar { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:12px; }
.date-tabs { display:flex; gap:8px; flex-wrap:wrap; }
.date-tab { padding:6px 14px; border-radius:20px; border:1px solid #ddd; background:white; cursor:pointer; font-size:12px; color:#666; }
.date-tab.active { background:#1a1a2e; color:white; border-color:#1a1a2e; }
.filter-tabs { display:flex; gap:6px; }
.filter-tab { padding:6px 14px; border-radius:20px; border:1px solid #ddd; background:white; cursor:pointer; font-size:12px; color:#666; }
.filter-tab.active { background:#4f8ef7; color:white; border-color:#4f8ef7; }
.post-table { width:100%; border-collapse:collapse; font-size:13px; }
.post-table th { background:#f8f9fa; padding:10px 12px; text-align:left; font-weight:600; color:#555; border-bottom:1px solid #eee; }
.post-table td { padding:10px 12px; border-bottom:1px solid #f0f0f0; vertical-align:middle; }
.post-table tr:hover { background:#fafafa; }
.post-table tr.published-row { opacity:0.5; }
.title-link { color:#4f8ef7; cursor:pointer; }
.title-link:hover { text-decoration:underline; }
.badge { display:inline-block; padding:3px 10px; border-radius:20px; font-size:11px; font-weight:600; }
.badge-eye{background:#e8f0fe;color:#4f8ef7;} .badge-lifting{background:#fff0e8;color:#f7934f;} .badge-nose{background:#e8faf3;color:#4fd19e;}
.badge-published { background:#e8fef0; color:#2ecc71; }
.badge-pending { background:#fff8e8; color:#f39c12; }
.check-btn { padding:5px 12px; border-radius:20px; border:none; cursor:pointer; font-size:11px; font-weight:600; transition:all 0.2s; }
.naver-btn { padding:5px 12px; border-radius:20px; border:none; cursor:pointer; font-size:11px; font-weight:600; background:#03C75A; color:white; transition:all 0.2s; }
.naver-btn:hover { background:#02a84b; }
.naver-btn:disabled { background:#ccc; cursor:not-allowed; }
.naver-btn { padding:5px 12px; border-radius:20px; border:none; cursor:pointer; font-size:11px; font-weight:600; background:#03C75A; color:white; transition:all 0.2s; }
.naver-btn:hover { background:#02a84b; }
.naver-btn:disabled { background:#ccc; cursor:not-allowed; }
.check-btn.pending { background:#fff8e8; color:#f39c12; border:1px solid #f39c12; }
.check-btn.published { background:#e8fef0; color:#2ecc71; border:1px solid #2ecc71; }
.keyword-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:16px; }
.kw-section h3 { font-size:13px; font-weight:600; margin-bottom:10px; color:#555; }
.kw-item { display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid #f0f0f0; font-size:12px; }
.kw-date { color:#aaa; font-size:11px; }
.empty { text-align:center; padding:40px; color:#aaa; font-size:13px; }
.modal-bg { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:1000; justify-content:center; align-items:center; }
.modal-bg.open { display:flex; }
.modal { background:white; border-radius:16px; width:760px; max-width:95vw; max-height:85vh; display:flex; flex-direction:column; }
.modal-header { padding:20px 24px; border-bottom:1px solid #eee; display:flex; justify-content:space-between; align-items:center; }
.modal-header h3 { font-size:16px; font-weight:600; color:#1a1a2e; }
.modal-close { background:none; border:none; font-size:22px; cursor:pointer; color:#888; }
.modal-body { padding:24px; overflow-y:auto; font-size:13px; line-height:1.9; color:#444; }
.modal-body p { margin-bottom:12px; white-space:pre-wrap; }
.modal-body .section-title { font-size:15px; font-weight:700; color:#1a1a2e; margin:20px 0 8px; border-left:3px solid #4f8ef7; padding-left:10px; }
.modal-body .faq-q { font-weight:600; color:#333; margin-top:12px; }
.modal-body .faq-a { color:#555; margin-left:8px; margin-bottom:8px; }
.card-images { display:flex; gap:12px; flex-wrap:wrap; margin-bottom:16px; }
.card-item { display:flex; flex-direction:column; align-items:center; gap:5px; }
.card-images img { width:120px; height:120px; object-fit:cover; border-radius:8px; cursor:pointer; border:1px solid #eee; display:block; }
.card-images img:hover { border-color:#4f8ef7; }
.copy-img-btn { padding:3px 10px; border-radius:12px; border:1px solid #ddd; background:#f8f9fa; font-size:11px; cursor:pointer; color:#555; transition:all 0.2s; white-space:nowrap; }
.copy-img-btn:hover { background:#4f8ef7; color:white; border-color:#4f8ef7; }
.copy-img-btn.copied { background:#2ecc71; color:white; border-color:#2ecc71; }
.inline-card { margin:10px 0 16px; }
.inline-card img { width:100%; max-width:400px; border-radius:10px; cursor:pointer; border:1px solid #eee; display:block; }
.inline-card img:hover { border-color:#4f8ef7; }
</style>
</head>
<body>

  <div style="background:#1a1a2e;display:flex;padding:0 24px;">
    <a href="/blog" style="padding:13px 22px;font-size:13px;color:#a78bfa;text-decoration:none;border-bottom:3px solid #a78bfa;display:block;">📝 블로그</a>
    <a href="/youtube" style="padding:13px 22px;font-size:13px;color:#a0a0c0;text-decoration:none;border-bottom:3px solid transparent;display:block;">🎬 유튜브 스크립트</a>
    <a href="/magazine" style="padding:13px 22px;font-size:13px;color:#a0a0c0;text-decoration:none;border-bottom:3px solid transparent;display:block;">📰 매거진</a>
    <a href="/cardnews" style="padding:13px 22px;font-size:13px;color:#a0a0c0;text-decoration:none;border-bottom:3px solid transparent;display:block;">🖼 카드뉴스</a>
    <a href="/threads" style="padding:13px 22px;font-size:13px;color:#a0a0c0;text-decoration:none;border-bottom:3px solid transparent;display:block;">🧵 스레드</a>
  </div>


  <!-- POP 탭 네비 -->
  <div style="background:#1a1a2e;border-bottom:2px solid rgba(167,139,250,0.2);padding:0 24px;display:flex;gap:0;position:sticky;top:0;z-index:999;">
    <a href="/blog" style="padding:13px 22px;font-size:13px;font-weight:500;color:#a0a0c0;text-decoration:none;border-bottom:3px solid transparent;margin-bottom:-2px;" id="tab-blog">📝 블로그</a>
    <a href="/youtube" style="padding:13px 22px;font-size:13px;font-weight:500;color:#a0a0c0;text-decoration:none;border-bottom:3px solid transparent;margin-bottom:-2px;" id="tab-youtube">🎬 유튜브 스크립트</a>
    <a href="/magazine" style="padding:13px 22px;font-size:13px;font-weight:500;color:#a0a0c0;text-decoration:none;border-bottom:3px solid transparent;margin-bottom:-2px;" id="tab-magazine">📰 매거진</a>
    <a href="/cardnews" style="padding:13px 22px;font-size:13px;font-weight:500;color:#a0a0c0;text-decoration:none;border-bottom:3px solid transparent;margin-bottom:-2px;" id="tab-cardnews">🖼 카드뉴스</a>
    <a href="/threads" style="padding:13px 22px;font-size:13px;font-weight:500;color:#a0a0c0;text-decoration:none;border-bottom:3px solid transparent;margin-bottom:-2px;" id="tab-threads">🧵 스레드</a>
  </div>
  <script>
    const _path = window.location.pathname;
    if(_path === '/' || _path === '') document.getElementById('tab-blog').style.cssText += ';color:#a78bfa;border-bottom-color:#a78bfa;';
    else if(_path.startsWith('/youtube')) document.getElementById('tab-youtube').style.cssText += ';color:#a78bfa;border-bottom-color:#a78bfa;';
    else if(_path.startsWith('/magazine')) document.getElementById('tab-magazine').style.cssText += ';color:#a78bfa;border-bottom-color:#a78bfa;';
    else if(_path.startsWith('/cardnews')) document.getElementById('tab-cardnews').style.cssText += ';color:#a78bfa;border-bottom-color:#a78bfa;';
    else if(_path.startsWith('/threads')) document.getElementById('tab-threads').style.cssText += ';color:#a78bfa;border-bottom-color:#a78bfa;';
  </script>

<div class="header">
  <h1>🏥 팝성형외과 블로그 대시보드</h1>
  <div style="display:flex;align-items:center;gap:16px;">
    <div id="nahyun-status" style="font-size:12px;padding:4px 12px;border-radius:20px;background:rgba(255,255,255,0.1);color:#aaa;">나현쌤 서버 확인 중...</div>
    <div id="current-date"></div>
  </div>
</div>
<div class="container">
  <div class="stats-row" id="stats-row"></div>
  <div class="section">
    <h2>📅 날짜별 현황</h2>
    <div class="top-bar">
      <div class="date-tabs" id="date-tabs"></div>
      <div class="filter-tabs">
        <button class="filter-tab active" onclick="setFilter('all', this)">전체</button>
        <button class="filter-tab" onclick="setFilter('pending', this)">미발행</button>
        <button class="filter-tab" onclick="setFilter('published', this)">발행완료</button>
      </div>
    </div>
    <div id="posts-area"></div>
  </div>
  <div class="section">
    <h2>✅ 발행완료 키워드 이력</h2>
    <div class="keyword-grid" id="keyword-grid"></div>
  </div>
</div>

<div class="modal-bg" id="modal-bg" onclick="closeModal(event)">
  <div class="modal">
    <div class="modal-header">
      <h3 id="modal-title"></h3>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="modal-body" id="modal-body"></div>
  </div>
</div>

<script>
let currentDate = null;
let allData = {};
let currentFilter = 'all';

async function loadData() {
  const res = await fetch('/api/data');
  allData = await res.json();
  render();
}

function render() {
  document.getElementById('current-date').textContent = new Date().toLocaleDateString('ko-KR',{year:'numeric',month:'long',day:'numeric',weekday:'short'});
  const tabs = document.getElementById('date-tabs');
  tabs.innerHTML = '';
  allData.dates.forEach((d, i) => {
    const btn = document.createElement('button');
    btn.className = 'date-tab' + (i===0?' active':'');
    btn.textContent = d.slice(4,6) + '/' + d.slice(6,8);
    btn.onclick = () => {
      currentDate = d;
      document.querySelectorAll('.date-tab').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');
      renderPosts(); renderStats();
    };
    tabs.appendChild(btn);
  });
  if (!currentDate && allData.dates.length > 0) currentDate = allData.dates[0];
  renderStats(); renderPosts(); renderKeywords();
}

function setFilter(f, el) {
  currentFilter = f;
  document.querySelectorAll('.filter-tab').forEach(b=>b.classList.remove('active'));
  el.classList.add('active');
  renderPosts();
}

function renderStats() {
  const posts = allData.posts_by_date[currentDate] || [];
  const eyeCount = posts.filter(function(p){return p.category==='\ub208\uc131\ud615';}).length;
  const liftCount = posts.filter(function(p){return p.category==='\ub9ac\ud504\ud305';}).length;
  const noseCount = posts.filter(function(p){return p.category==='\ucf54\uc131\ud615';}).length;
  const pubCount = posts.filter(function(p){return p.published;}).length;
  var h = '';
  h += '<div class="stat-card"><div class="label">' + '\uc804\uccb4 / \ubc1c\ud589\uc644\ub8cc' + '</div>';
  h += '<div class="value">' + posts.length + ' <span style="font-size:16px;color:#2ecc71">/ ' + pubCount + '</span></div>';
  h += '<div class="sub">' + '\ubaa9\ud45c 26\uac1c' + '</div>';
  h += '<div class="progress-bar"><div class="fill fill-total" style="width:' + Math.min(posts.length/26*100,100) + '%"></div></div></div>';
  h += '<div class="stat-card"><div class="label">\ud83d\udc41 \ub208\uc131\ud615</div><div class="value">' + eyeCount + '</div>';
  h += '<div class="sub">\ubaa9\ud45c 13\uac1c</div><div class="progress-bar"><div class="fill fill-eye" style="width:' + Math.min(eyeCount/13*100,100) + '%"></div></div></div>';
  h += '<div class="stat-card"><div class="label">\u2728 \ub9ac\ud504\ud305</div><div class="value">' + liftCount + '</div>';
  h += '<div class="sub">\ubaa9\ud45c 9\uac1c</div><div class="progress-bar"><div class="fill fill-lifting" style="width:' + Math.min(liftCount/9*100,100) + '%"></div></div></div>';
  h += '<div class="stat-card"><div class="label">\ud83d\udc43 \ucf54\uc131\ud615</div><div class="value">' + noseCount + '</div>';
  h += '<div class="sub">\ubaa9\ud45c 4\uac1c</div><div class="progress-bar"><div class="fill fill-nose" style="width:' + Math.min(noseCount/4*100,100) + '%"></div></div></div>';
  document.getElementById('stats-row').innerHTML = h;
}

function renderPosts() {
  var posts = allData.posts_by_date[currentDate] || [];
  if (currentFilter === 'pending') posts = posts.filter(function(p){return !p.published;});
  if (currentFilter === 'published') posts = posts.filter(function(p){return p.published;});
  var area = document.getElementById('posts-area');
  if (posts.length === 0) { area.innerHTML = '<div class="empty">\ud574\ub2f9 \uae00\uc774 \uc5c6\uc2b5\ub2c8\ub2e4</div>'; return; }
  var bc = {'\ub208\uc131\ud615':'badge-eye', '\ub9ac\ud504\ud305':'badge-lifting', '\ucf54\uc131\ud615':'badge-nose'};
  var rows = '';
  for (var i = 0; i < posts.length; i++) {
    var p = posts[i];
    var cat = p.category || '-';
    var badgeClass = bc[cat] || '';
    var completedBadge = p.completed ? ' <span style="font-size:10px;color:#2ecc71;background:#e8fef0;padding:2px 6px;border-radius:10px;">\uc800\uc7a5\uc644\ub8cc</span>' : '';
    var pubBtn = p.published
      ? '<button class="check-btn published" onclick="togglePublished(\'' + p.post_id + '\', this)">\u2705 \ubc1c\ud589\uc644\ub8cc</button>'
      : '<button class="check-btn pending" onclick="togglePublished(\'' + p.post_id + '\', this)">\u2b1c \ubbf8\ubc1c\ud589</button>';
    rows += '<tr class="' + (p.published?'published-row':'') + '">';
    rows += '<td>' + (i+1) + '</td>';
    rows += '<td><span class="badge ' + badgeClass + '">' + cat + '</span></td>';
    rows += '<td>' + (p.keyword||'-') + '</td>';
    rows += '<td><span class="title-link" onclick="openModal(\'' + p.post_id + '\')">' + (p.title||'-') + '</span>' + completedBadge + '</td>';
    rows += '<td>' + pubBtn + '</td>';
    rows += '<td><button class="naver-btn" onclick="naverUpload(\'' + p.category + '\',\'' + p.date + '\', this)">\ub124\uc774\ubc84 \uc5c5\ub85c\ub4dc</button></td>';
    rows += '</tr>';
  }
  area.innerHTML = '<table class="post-table"><thead><tr><th>#</th><th>\uce74\ud14c\uace0\ub9ac</th><th>\ud0a4\uc6cc\ub4dc</th><th>\uc81c\ubaa9</th><th>\ubc1c\ud589</th><th>\ub124\uc774\ubc84</th></tr></thead><tbody>' + rows + '</tbody></table>';
}

async function naverUpload(category, date, btn) {
  if (!confirm(category + ' 카테고리 네이버 업로드를 시작할까요?\n(브라우저 창이 열리고 자동으로 진행됩니다)')) return;
  btn.disabled = true;
  btn.textContent = '실행 중...';
  try {
    const res = await fetch('/api/naver_upload', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({category, date})
    });
    const data = await res.json();
    if (data.ok) {
      btn.textContent = '✓ 실행됨';
      btn.style.background = '#4f8ef7';
    } else {
      btn.textContent = '오류';
      btn.style.background = '#e74c3c';
      alert('오류: ' + data.error);
    }
  } catch(e) {
    btn.textContent = '오류';
    btn.style.background = '#e74c3c';
    alert('서버 연결 실패');
  }
}

async function togglePublished(postId, btn) {
  const res = await fetch('/api/toggle_published', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({post_id: postId})
  });
  const data = await res.json();
  for (const date in allData.posts_by_date) {
    allData.posts_by_date[date].forEach(function(p) {
      if (p.post_id === postId) p.published = data.published;
    });
  }
  renderPosts(); renderStats(); renderKeywords();
}

function formatContent(content, cards) {
  if (!content) return '';
  cards = cards || [];
  const lines = content.split('\n');
  let html = '';

  // 카드 전체 맨 위에 모아서 출력
  if (cards.length > 0) {
    html += '<div class="card-images">';
    for (let ci = 0; ci < cards.length; ci++) {
      const src = cards[ci];
      html += '<div class="card-item">';
      html += '<img src="' + src + '" onclick="window.open(\'' + src + '\',\'_blank\')" title="카드뉴스 ' + (ci+1) + ' (클릭: 새탭)">';
      html += '<button class="copy-img-btn" onclick="copyImage(\'' + src + '\', this)">📋 복사</button>';
      html += '</div>';
    }
    html += '</div>';
  }

  for (let i = 0; i < lines.length; i++) {
    const t = lines[i].trim();
    if (!t) { html += '<br>'; continue; }
    if (/^={3,}$/.test(t)) continue;
    const prefix = t.split(':')[0];
    if (['\uce74\ud14c\uace0\ub9ac','\ud0a4\uc6cc\ub4dc','\uc81c\ubaa9','\uc0dd\uc131\uc77c','\uac80\uc99d\uc0c1\ud0dc','\uac80\uc99d\uc810\uc218','\uac80\uc99d\uc774\uc288'].indexOf(prefix) >= 0) continue;
    if (t.indexOf('## ') === 0) {
      html += '<div class="section-title">' + t.substring(3) + '</div>';
    } else if (/^Q[0-9]+\./.test(t)) {
      html += '<div class="faq-q">' + t + '</div>';
    } else if (/^A[0-9]+\./.test(t)) {
      html += '<div class="faq-a">' + t + '</div>';
    } else {
      html += '<p>' + t + '</p>';
    }
  }
  return html;
}

async function openModal(postId) {
  for (const date in allData.posts_by_date) {
    const post = allData.posts_by_date[date].find(function(p){return p.post_id===postId;});
    if (post) {
      document.getElementById('modal-title').textContent = post.title || post.keyword;
      let cards = [];
      try {
        const res = await fetch('/api/cards?filename=' + encodeURIComponent(post.filename) + '&date=' + post.date);
        cards = await res.json();
      } catch(e) {}
      document.getElementById('modal-body').innerHTML = formatContent(post.content || '', cards);
      document.getElementById('modal-bg').classList.add('open');
      return;
    }
  }
}

async function copyImage(src, btn) {
  try {
    const res = await fetch(src);
    const blob = await res.blob();
    const pngBlob = await new Promise((resolve) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        canvas.width = img.naturalWidth;
        canvas.height = img.naturalHeight;
        canvas.getContext('2d').drawImage(img, 0, 0);
        canvas.toBlob(resolve, 'image/png');
      };
      img.src = URL.createObjectURL(blob);
    });
    await navigator.clipboard.write([
      new ClipboardItem({ 'image/png': pngBlob })
    ]);
    btn.textContent = '✅ 복사됨';
    btn.classList.add('copied');
    setTimeout(() => { btn.textContent = '📋 복사'; btn.classList.remove('copied'); }, 2000);
  } catch(e) {
    // 클립보드 API 실패 시 새 탭으로 fallback
    window.open(src, '_blank');
    btn.textContent = '↗ 새탭열림';
    setTimeout(() => { btn.textContent = '📋 복사'; }, 2000);
  }
}

function closeModal(e) {
  if (!e || e.target===document.getElementById('modal-bg')) {
    document.getElementById('modal-bg').classList.remove('open');
  }
}

function renderKeywords() {
  const used = allData.used_keywords;
  const labels = {eye:'\ud83d\udc41 \ub208\uc131\ud615', lifting:'\u2728 \ub9ac\ud504\ud305', nose:'\ud83d\udc43 \ucf54\uc131\ud615'};
  let html = '';
  for (const cat in used) {
    const items = used[cat];
    let rows = '';
    if (items.length === 0) {
      rows = '<div class="empty" style="padding:20px">\ubc1c\ud589\uc644\ub8cc \uc774\ub825 \uc5c6\uc74c</div>';
    } else {
      const slice = items.slice(0,20);
      for (let i = 0; i < slice.length; i++) {
        rows += '<div class="kw-item"><span>' + slice[i].keyword + '</span><span class="kw-date">' + slice[i].date.slice(4,6) + '/' + slice[i].date.slice(6,8) + '</span></div>';
      }
    }
    html += '<div class="kw-section"><h3>' + labels[cat] + ' (' + items.length + '\uac1c \ubc1c\ud589\uc644\ub8cc)</h3>' + rows + '</div>';
  }
  document.getElementById('keyword-grid').innerHTML = html;
}

async function naverUpload(category, date, btn) {
  if (!confirm(category + ' 카테고리 네이버 업로드를 시작할까요?\n나현쌤 컴에서 브라우저가 열립니다.')) return;
  btn.disabled = true;
  btn.textContent = '전송 중...';
  try {
    const res = await fetch('/api/naver_upload', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({category, date})
    });
    const data = await res.json();
    if (data.ok) {
      btn.textContent = '✓ 전송됨';
      btn.style.background = '#4f8ef7';
    } else {
      btn.textContent = '오류';
      btn.style.background = '#e74c3c';
      btn.disabled = false;
      alert('오류: ' + data.error);
    }
  } catch(e) {
    btn.textContent = '오류';
    btn.style.background = '#e74c3c';
    btn.disabled = false;
    alert('서버 연결 실패');
  }
}

async function checkNahyunStatus() {
  try {
    const res = await fetch('/api/nahyun_status');
    const data = await res.json();
    const el = document.getElementById('nahyun-status');
    if (!el) return;
    if (data.running) {
      el.style.background = 'rgba(79,142,247,0.3)';
      el.style.color = '#7ec8ff';
      el.textContent = '🔄 나현쌤: ' + data.message;
    } else if (data.message && data.message.includes('오프라인')) {
      el.style.background = 'rgba(255,100,100,0.2)';
      el.style.color = '#ff9999';
      el.textContent = '⚫ 나현쌤 서버 오프라인';
    } else {
      el.style.background = 'rgba(46,204,113,0.2)';
      el.style.color = '#2ecc71';
      el.textContent = '✅ 나현쌤: ' + (data.message || '대기 중');
    }
  } catch(e) {}
}

loadData();
setInterval(loadData, 30000);
setInterval(checkNahyunStatus, 5000);
checkNahyunStatus();
</script>
</body>
</html>
"""


HOME_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>팝성형외과 콘텐츠 허브</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI','Noto Sans KR',sans-serif;background:#f0f2f5;color:#1a1a2e;min-height:100vh}
.nav{background:#1a1a2e;display:flex;padding:0 24px;position:sticky;top:0;z-index:100}
.nav a{padding:13px 20px;font-size:13px;color:#a0a0c0;text-decoration:none;border-bottom:3px solid transparent;display:block}
.nav a:hover{color:#a78bfa}
.nav a.on{color:#a78bfa;border-bottom-color:#a78bfa}
.header{background:linear-gradient(135deg,#1a1a2e,#16213e);color:#fff;padding:32px 40px 28px}
.header h1{font-size:22px;font-weight:700;margin-bottom:6px}
.header p{font-size:13px;color:#8888aa}
.wrap{max-width:1100px;margin:0 auto;padding:36px 24px}
.auto-badge{display:inline-flex;align-items:center;gap:6px;background:rgba(167,139,250,.12);border:1px solid rgba(167,139,250,.25);color:#a78bfa;border-radius:20px;padding:5px 12px;font-size:12px;margin-bottom:28px}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}
.card{background:#fff;border-radius:16px;padding:28px;box-shadow:0 2px 12px rgba(0,0,0,.06);display:flex;flex-direction:column;gap:0;cursor:default;transition:box-shadow .2s}
.card:hover{box-shadow:0 6px 24px rgba(0,0,0,.1)}
.card-icon{width:44px;height:44px;background:#f5f5f7;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:20px;margin-bottom:18px}
.card h2{font-size:18px;font-weight:700;margin-bottom:6px}
.card .desc{font-size:13px;color:#6b7280;margin-bottom:20px;line-height:1.6}
.features{display:flex;flex-direction:column;gap:0;border-top:1px solid #f3f4f6;padding-top:16px;margin-bottom:20px}
.feat{display:flex;align-items:center;gap:8px;padding:9px 0;border-bottom:1px solid #f9fafb;font-size:13px;color:#374151;text-decoration:none}
.feat:hover{color:#6355e8}
.feat-icon{font-size:14px;width:20px;text-align:center}
.feat-extra{font-size:12px;color:#9ca3af;margin-left:auto}
.btn{display:block;margin-top:auto;padding:12px 0;background:#1a1a2e;color:#fff;text-align:center;border-radius:10px;font-size:14px;font-weight:600;text-decoration:none;transition:background .2s}
.btn:hover{background:#2d2d4e}
.btn.accent{background:linear-gradient(135deg,#6355e8,#5b4fe8)}
.btn.accent:hover{background:linear-gradient(135deg,#5448d4,#4e43d4)}

/* SOV 실시간 위젯 */
.sov-bar{background:#fff;border-radius:12px;padding:20px 28px;box-shadow:0 2px 8px rgba(0,0,0,.06);margin-bottom:24px;display:flex;align-items:center;gap:32px;flex-wrap:wrap}
.sov-num{font-size:40px;font-weight:800;color:#1a1a2e;line-height:1}
.sov-label{font-size:12px;color:#9ca3af;margin-top:4px}
.sov-models{display:flex;gap:20px;flex:1}
.sov-model{text-align:center}
.sov-model .val{font-size:18px;font-weight:700;color:#1a1a2e}
.sov-model .name{font-size:11px;color:#9ca3af;margin-top:2px}
.sov-model .rank{font-size:11px;color:#a78bfa;margin-top:1px}
.sov-actions{margin-left:auto;display:flex;gap:8px}
.sov-btn{padding:8px 16px;border-radius:8px;font-size:12px;font-weight:600;border:none;cursor:pointer;transition:all .2s}
.sov-btn.measure{background:#1a1a2e;color:#fff}
.sov-btn.measure:hover{background:#2d2d4e}
.sov-btn.detail{background:#f3f4f6;color:#374151}
.sov-btn.detail:hover{background:#e5e7eb}
.loading{color:#9ca3af;font-size:13px}
</style>
</head>
<body>
<div class="nav">
  <a href="/" class="on">🏠 홈</a>
  <a href="/blog">📝 블로그</a>
  <a href="/youtube">🎬 유튜브</a>
  <a href="/magazine">📰 매거진</a>
  <a href="/cardnews">🖼 카드뉴스</a>
  <a href="/threads">🧵 스레드</a>
</div>
<div class="header">
  <h1>팝성형외과 콘텐츠 허브</h1>
  <p>AI 검색 노출 분석 / 콘텐츠 자동화 / 발행 관리</p>
</div>
<div class="wrap">

  <!-- SOV 실시간 바 -->
  <div class="sov-bar" id="sovBar">
    <div>
      <div class="sov-num" id="sovPct">--%</div>
      <div class="sov-label">Share of Voice</div>
    </div>
    <div class="sov-models" id="sovModels">
      <div class="loading">측정 데이터 로딩 중...</div>
    </div>
    <div class="sov-actions">
      <button class="sov-btn measure" onclick="measureSOV()">▶ 지금 측정</button>
      <button class="sov-btn detail" onclick="location.href='/sov'">상세 보기 -></button>
    </div>
  </div>

  <!-- 4단계 진행 가이드 -->
  <div class="guide-wrap" style="background:#fff;border-radius:14px;padding:24px 28px;box-shadow:0 2px 10px rgba(0,0,0,.06);margin-bottom:24px">
    <div style="font-size:11px;color:#9ca3af;font-weight:600;letter-spacing:.08em;margin-bottom:12px">무료 체험 가이드</div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <div style="font-size:16px;font-weight:700;color:#1a1a2e" id="guide-progress-text">단계 진행 중</div>
      <a href="/sov" style="font-size:12px;color:#a78bfa;text-decoration:none">안내 슬라이드 먼저 보기 ▶</a>
    </div>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px" id="guide-steps">
      <div class="guide-step done" onclick="location.href='/sov'" style="padding:14px;border-radius:10px;border:1px solid #e5e7eb;cursor:pointer;transition:all .2s">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <span style="font-size:10px;color:#9ca3af;font-weight:600">분석</span>
          <span style="font-size:16px">📋</span>
        </div>
        <div style="font-size:13px;font-weight:600;color:#1a1a2e">GEO 초기 세팅</div>
      </div>
      <div class="guide-step done" onclick="location.href='/sov'" style="padding:14px;border-radius:10px;border:1px solid #e5e7eb;cursor:pointer;transition:all .2s">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <span style="font-size:10px;color:#9ca3af;font-weight:600">분석</span>
          <span style="font-size:16px">📊</span>
        </div>
        <div style="font-size:13px;font-weight:600;color:#1a1a2e">AI 점유율 진단</div>
      </div>
      <div class="guide-step done" onclick="location.href='/content_ai'" style="padding:14px;border-radius:10px;border:1px solid #e5e7eb;cursor:pointer;transition:all .2s">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <span style="font-size:10px;color:#9ca3af;font-weight:600">분석</span>
          <span style="font-size:16px">✏️</span>
        </div>
        <div style="font-size:13px;font-weight:600;color:#1a1a2e">GEO 콘텐츠 작성</div>
      </div>
      <div class="guide-step active" onclick="location.href='/blog'" style="padding:14px;border-radius:10px;border:2px solid #a78bfa;background:#f5f3ff;cursor:pointer;transition:all .2s">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <span style="font-size:10px;color:#a78bfa;font-weight:600">발행</span>
          <span style="font-size:16px">🚀</span>
        </div>
        <div style="font-size:13px;font-weight:700;color:#1a1a2e">콘텐츠 발행</div>
      </div>
    </div>
    <div style="margin-top:14px;display:flex;justify-content:space-between;align-items:center">
      <div style="font-size:12px;color:#a78bfa">지금은 <strong>발행 카드</strong>에서 한 번 실행할 단계예요</div>
      <a href="/blog" style="padding:8px 16px;background:#1a1a2e;color:#fff;border-radius:8px;font-size:12px;font-weight:600;text-decoration:none">발행 카드 위치 보기 -></a>
    </div>
  </div>

  <!-- 주간 자동화 캘린더 -->
  <div style="background:#fff;border-radius:14px;padding:24px 28px;box-shadow:0 2px 10px rgba(0,0,0,.06);margin-bottom:24px">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <div>
        <div style="font-size:11px;color:#9ca3af;font-weight:600;margin-bottom:4px">🗓 이번 주 자동화 / 분석/콘텐츠 통합</div>
        <div style="display:flex;align-items:center;gap:12px">
          <span style="font-size:16px;font-weight:700;color:#1a1a2e" id="week-label">이번 주</span>
        </div>
      </div>
      <button onclick="location.href='/sov'" style="padding:8px 16px;background:#1a1a2e;color:#fff;border:none;border-radius:8px;font-size:12px;font-weight:600;cursor:pointer">🔄 자동화 미리보기 -></button>
    </div>
    <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:8px" id="week-calendar">
    </div>
  </div>

  <div class="auto-badge">🔄 이번 주 자동화 / 분석/콘텐츠 통합</div>

  <!-- 3단계 카드 -->
  <div class="cards">

    <!-- 1. 분석 -->
    <div class="card">
      <div class="card-icon">📊</div>
      <h2>분석</h2>
      <p class="desc">AI 검색에서 팝성형외과가 얼마나 노출되는지 파악해요</p>
      <div class="features">
        <a href="/sov" class="feat"><span class="feat-icon">📈</span> 노출 점유율 <span class="feat-extra" id="feat-sov">--</span></a>
        <a href="/sov#prompts" class="feat"><span class="feat-icon">💬</span> 프롬프트 <span class="feat-extra" id="feat-prompt">오늘 --개</span></a>
        <a href="/sov#keywords" class="feat"><span class="feat-icon">🔍</span> AI 검색 키워드 <span class="feat-extra" id="feat-kw">--</span></a>
        <a href="/sov#ranking" class="feat"><span class="feat-icon">🏆</span> 경쟁사 랭킹</a>
      </div>
      <a href="/sov" class="btn">노출 확인하기 -></a>
    </div>

    <!-- 2. 실행 -->
    <div class="card">
      <div class="card-icon">⚡</div>
      <h2>실행</h2>
      <p class="desc">콘텐츠를 만들고 AI 인용 기회를 발굴해요</p>
      <div class="features">
        <a href="/blog" class="feat"><span class="feat-icon">📝</span> 블로그 생성 <span class="feat-extra" id="feat-blog">오늘 --개</span></a>
        <a href="/magazine" class="feat"><span class="feat-icon">📰</span> 매거진 생성 <span class="feat-extra" id="feat-mag">오늘 --개</span></a>
        <a href="/youtube" class="feat"><span class="feat-icon">🎬</span> 유튜브 스크립트 <span class="feat-extra" id="feat-yt">오늘 --개</span></a>
        <a href="/cardnews" class="feat"><span class="feat-icon">🖼</span> 카드뉴스</a>
      </div>
      <a href="/blog" class="btn accent">콘텐츠 만들기 -></a>
    </div>

    <!-- 3. 발행 -->
    <div class="card">
      <div class="card-icon">🚀</div>
      <h2>발행</h2>
      <p class="desc">완성된 콘텐츠를 내보내고 AI 유입을 추적해요</p>
      <div class="features">
        <a href="/blog" class="feat"><span class="feat-icon">📋</span> 콘텐츠 관리 <span class="feat-extra" id="feat-pub">발행 --개</span></a>
        <a href="/threads" class="feat"><span class="feat-icon">🧵</span> 스레드 발행</a>
        <a href="/sov#keywords" class="feat"><span class="feat-icon">🤖</span> AI 봇 유입 분석</a>
        <a href="/magazine" class="feat"><span class="feat-icon">✨</span> 매거진 발행</a>
      </div>
      <div style="display:flex;gap:8px;margin-top:auto;flex-direction:column">
        <button class="btn" style="background:#4f46e5" id="blogGenBtn" onclick="generateBlog()">📝 블로그 글 생성 (하루치)</button>
        <button class="btn" style="background:#7c3aed" id="magGenBtn" onclick="generateMag()">📰 매거진 글 생성 (하루치)</button>
      </div>
    </div>

  </div>
</div>

<script>
async function loadSOV() {
  try {
    const r = await fetch('/api/sov/today');
    const d = await r.json();
    const s = d.summary || {};
    const pct = s.overall_sov_pct ?? s.sov_pct ?? 0;
    document.getElementById('sovPct').textContent = s.total_prompts > 0 ? pct + '%' : '--%';
    document.getElementById('feat-sov').textContent = s.total_prompts > 0 ? pct + '%' : '미측정';

    // 모델별
    const models = d.models || {};
    const labels = {perplexity:'Perplexity', gemini:'Gemini', chatgpt:'ChatGPT'};
    const el = document.getElementById('sovModels');
    if (Object.keys(models).length) {
      el.innerHTML = Object.entries(models).map(([k,m]) => {
        const measured = m.measured > 0;
        const sov      = measured ? m.sov_pct + '%' : '미측정';
        const rankStr  = m.our_rank ? '#' + m.our_rank + '위' : (measured ? '미언급' : '');
        return `<div class="sov-model">
          <div class="val">${sov}</div>
          <div class="name">${labels[k]||k}</div>
          <div class="rank">${rankStr}</div>
        </div>`;
      }).join('');
    } else {
      el.innerHTML = '<div class="loading">측정 버튼을 눌러주세요</div>';
    }
  } catch(e) {
    document.getElementById('sovModels').innerHTML = '<div class="loading">데이터 없음</div>';
  }
}

async function loadStats() {
  try {
    // 프롬프트
    const pr = await fetch('/api/prompts/today');
    const pd = await pr.json();
    document.getElementById('feat-prompt').textContent = '오늘 ' + (pd.total||0) + '개';
    document.getElementById('feat-kw').textContent = (pd.prompts||[]).length + '개 키워드';
  } catch(e) {}

  try {
    // 발행 수 (블로그 데이터에서)
    const br = await fetch('/api/data');
    const bd = await br.json();
    const dates = bd.dates || [];
    const today = new Date().toISOString().slice(0,10).replace(/-/g,'');
    const todayPosts = (bd.posts_by_date || {})[today] || [];
    const blogCount = todayPosts.length;
    const pubCount  = todayPosts.filter(p => p.published).length;
    document.getElementById('feat-blog').textContent = '오늘 ' + blogCount + '개';
    document.getElementById('feat-pub').textContent  = '발행 ' + pubCount + '개';
  } catch(e) {}

  try {
    // 유튜브
    const yr = await fetch('/api/yt/scripts');
    const yd = await yr.json();
    const today = new Date().toISOString().slice(0,10).replace(/-/g,'');
    const ytToday = yd.filter(s => (s.date||'').startsWith(today)).length;
    document.getElementById('feat-yt').textContent = '오늘 ' + ytToday + '개';
  } catch(e) {}

  try {
    // 매거진
    const mr = await fetch('/api/mag/data');
    const md = await mr.json();
    const dates = md.dates || [];
    const today = new Date().toISOString().slice(0,10).replace(/-/g,'');
    const todayMag = ((md.posts_by_date||{})[today]||[]).length;
    document.getElementById('feat-mag').textContent = '오늘 ' + todayMag + '개';
  } catch(e) {}
}

async function measureSOV() {
  const btn = document.querySelector('.sov-btn.measure');
  btn.disabled = true; btn.textContent = '측정 중...';
  try {
    const r = await fetch('/api/sov/measure', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({force:false})});
    const d = await r.json();
    if (d.success) { await loadSOV(); }
    else alert('측정 실패: ' + d.error);
  } catch(e) { alert('오류: ' + e.message); }
  finally { btn.disabled=false; btn.textContent='▶ 지금 측정'; }
}

loadSOV();
loadStats();

async function generateBlog() {
  const btn = document.getElementById('blogGenBtn');
  btn.disabled = true;
  btn.textContent = '⏳ 블로그 생성 중... (수 분 소요)';
  btn.style.background = '#6b7280';
  try {
    const r = await fetch('/api/blog/generate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({category: 'all'})
    });
    const d = await r.json();
    if (d.success) {
      btn.style.background = '#16a34a';
      btn.textContent = '✅ 블로그 생성 완료!';
      await loadStats();
      setTimeout(() => {
        btn.style.background = '#4f46e5';
        btn.textContent = '📝 블로그 글 생성 (하루치)';
      }, 3000);
    } else {
      alert('실패: ' + (d.error || ''));
    }
  } catch(e) { alert('오류: ' + e.message); }
  finally { btn.disabled = false; }
}

async function generateMag() {
  const btn = document.getElementById('magGenBtn');
  btn.disabled = true;
  btn.textContent = '⏳ 매거진 생성 중... (수 분 소요)';
  btn.style.background = '#6b7280';
  try {
    const r = await fetch('/api/magazine/generate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({category: 'all'})
    });
    const d = await r.json();
    if (d.success) {
      btn.style.background = '#16a34a';
      btn.textContent = '✅ 매거진 생성 완료!';
      await loadStats();
      setTimeout(() => {
        btn.style.background = '#7c3aed';
        btn.textContent = '📰 매거진 글 생성 (하루치)';
      }, 3000);
    } else {
      alert('실패: ' + (d.error || ''));
    }
  } catch(e) { alert('오류: ' + e.message); }
  finally { btn.disabled = false; }
}
</script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HOME_HTML)

@app.route('/blog')
def index():
    return render_template_string(HTML)


# -- 홈에서 블로그/매거진 생성 버튼 API ----------------------------

BLOG_RUN_PATH = BASE_DIR / "run.py"
MAGAZINE_RUN_PATH = BASE_DIR / "magazine_run.py"

@app.route('/api/blog/generate', methods=['POST'])
def api_blog_generate():
    import subprocess as _sp
    try:
        data = request.get_json() or {}
        category = data.get('category', 'all')
        if category == 'all':
            cmd = ['python', 'run.py']
        else:
            cmd = ['python', 'run.py', '--category', category]
        result = _sp.run(
            cmd, cwd=str(BASE_DIR),
            capture_output=True, text=True, timeout=900
        )
        if result.returncode != 0:
            return jsonify({'success': False, 'error': result.stderr[-1000:]})
        return jsonify({'success': True, 'output': result.stdout[-500:]})
    except _sp.TimeoutExpired:
        return jsonify({'success': False, 'error': '블로그 생성 시간 초과'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/magazine/generate', methods=['POST'])
def api_magazine_generate_home():
    import subprocess as _sp
    try:
        data = request.get_json() or {}
        category = data.get('category', 'all')
        if category == 'all':
            cmd = ['python', 'magazine_run.py']
        else:
            cmd = ['python', 'magazine_run.py', '--category', category, '--count', '1', '--additive']
        result = _sp.run(
            cmd, cwd=str(MAGAZINE_RUN_PATH.parent),
            capture_output=True, text=True, timeout=900
        )
        if result.returncode != 0:
            return jsonify({'success': False, 'error': result.stderr[-1000:]})
        return jsonify({'success': True, 'output': result.stdout[-500:]})
    except _sp.TimeoutExpired:
        return jsonify({'success': False, 'error': '매거진 생성 시간 초과'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})




@app.route('/api/data')
def api_data():
    dates = get_available_dates()
    posts_by_date = {}
    for d in dates:
        posts_by_date[d] = get_posts(d)
    return jsonify({
        "dates": dates,
        "posts_by_date": posts_by_date,
        "used_keywords": get_used_keywords(),
    })

@app.route('/api/naver_upload', methods=['POST'])
def naver_upload():
    import urllib.request as urlreq
    import os
    data = request.get_json()
    category = data.get('category', 'eye')
    date_str = data.get('date', datetime.now().strftime('%Y%m%d'))

    cat_map = {'눈성형': 'eye', '리프팅': 'lifting', '코성형': 'nose'}
    cat_en = cat_map.get(category, category)

    nahyun_url = os.environ.get('NAHYUN_SERVER_URL', '')
    if not nahyun_url:
        return jsonify({"ok": False, "error": ".env에 NAHYUN_SERVER_URL이 없어요"}), 500

    # 해당 날짜+카테고리 미완료 글 수집
    posts = get_posts(date_str)
    target = [p for p in posts if not p.get('completed') and p.get('category') == category]

    if not target:
        return jsonify({"ok": False, "error": "업로드할 글이 없어요"}), 400

    def extract_body(content):
        skip = ('카테고리:', '키워드:', '제목:', '생성일:', '검증상태:', '검증점수:', '검증이슈:', '===')
        lines = [l for l in content.split('\n') if not any(l.strip().startswith(s) for s in skip)]
        return '\n'.join(lines).strip()

    payload = [{"title": p.get("title",""), "body": extract_body(p.get("content","")), "category_en": cat_en} for p in target]

    try:
        body_bytes = json.dumps({"posts": payload}, ensure_ascii=False).encode("utf-8")
        req = urlreq.Request(f"{nahyun_url.rstrip('/')}/upload", data=body_bytes, headers={"Content-Type": "application/json"}, method="POST")
        with urlreq.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        msg = f"{len(payload)}개 전송"
        return jsonify({"ok": True, "message": msg, "nahyun": result})
    except Exception as e:
        return jsonify({"ok": False, "error": f"나현쌤 서버 연결 실패: {str(e)}"}), 500

@app.route('/api/nahyun_status', methods=['GET'])
def nahyun_status():
    import urllib.request as urlreq
    import os
    nahyun_url = os.environ.get('NAHYUN_SERVER_URL', '')
    if not nahyun_url:
        return jsonify({"running": False, "message": "NAHYUN_SERVER_URL 미설정"})
    try:
        req = urlreq.Request(f"{nahyun_url.rstrip('/')}/status")
        with urlreq.urlopen(req, timeout=5) as resp:
            return jsonify(json.loads(resp.read().decode("utf-8")))
    except:
        return jsonify({"running": False, "message": "나현쌤 서버 오프라인"})

@app.route('/api/toggle_published', methods=['POST'])
def toggle_published():
    data = request.get_json()
    post_id = data.get('post_id')
    published = load_published()
    published[post_id] = not published.get(post_id, False)
    save_published(published)
    return jsonify({"published": published[post_id]})

@app.route('/api/cards')
def api_cards():
    """카드뉴스 PNG 경로 반환"""
    filename = request.args.get('filename', '')
    date = request.args.get('date', '')
    if not filename or not date:
        return jsonify([])

    # 파일명에서 stem 추출 (확장자 제거)
    stem = Path(filename).stem
    # 폴더명 형태: {date}_{stem} (예: 20260609_eye_01_이수경)
    folder_name = f"{date}_{stem}"
    card_dir = BASE_DIR / "cards" / date / folder_name
    if not card_dir.exists():
        # fallback: stem만으로도 시도
        card_dir = BASE_DIR / "cards" / date / stem
        folder_name = stem
    if not card_dir.exists():
        return jsonify([])

    cards = sorted(card_dir.glob("card_*.png"))
    return jsonify([f"/cards/{date}/{folder_name}/{c.name}" for c in cards])

@app.route('/cards/<date>/<folder_name>/<filename>')
def serve_card(date, folder_name, filename):
    """카드뉴스 이미지 정적 서빙"""
    from flask import send_from_directory
    card_dir = BASE_DIR / "cards" / date / folder_name
    return send_from_directory(str(card_dir), filename)





# ════════════════════════════════════════════
# 유튜브 스크립트 대시보드
# ════════════════════════════════════════════

YT_DIR = "C:/Users/USER/Desktop/youtube_script"
YT_OUTPUT = "C:/Users/USER/Desktop/youtube_script/output"

YT_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>POP 유튜브 스크립트</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
body{background:#f5f5f7;color:#1a1a2e;font-family:'Noto Sans KR',sans-serif;min-height:100vh}
.topnav{background:#1a1a2e;display:flex;padding:0 24px}
.topnav a{padding:13px 22px;font-size:13px;color:#a0a0c0;text-decoration:none;border-bottom:3px solid transparent;display:block}
.topnav a:hover{color:#a78bfa}
.topnav a.on{color:#a78bfa;border-bottom-color:#a78bfa}
.header{background:#fff;border-bottom:1px solid rgba(0,0,0,0.08);padding:14px 24px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}
.logo{font-size:17px;font-weight:700;color:#7c6af7}
.logo span{color:#8888a8;font-weight:300}
.btn-gen{background:linear-gradient(135deg,#6355e8,#5b4fe8);color:#fff;border:none;padding:9px 18px;border-radius:8px;font-size:13px;font-family:'Noto Sans KR',sans-serif;font-weight:500;cursor:pointer;transition:all .2s}
.btn-gen:disabled{opacity:.5;cursor:not-allowed}
.filterbar{background:#fff;border-bottom:1px solid rgba(0,0,0,0.08);padding:12px 24px;display:flex;gap:8px}
.tab{padding:6px 14px;border-radius:6px;font-size:13px;cursor:pointer;border:1px solid rgba(0,0,0,0.08);color:#8888a8;background:transparent;font-family:'Noto Sans KR',sans-serif;transition:all .2s}
.tab.on{background:#6355e8;border-color:#6355e8;color:#fff}
.main{display:grid;grid-template-columns:320px 1fr;height:calc(100vh - 120px)}
.listpanel{border-right:1px solid rgba(0,0,0,0.08);overflow-y:auto;background:#fff}
.listitem{padding:14px 18px;border-bottom:1px solid rgba(0,0,0,0.06);cursor:pointer;transition:background .15s}
.listitem:hover{background:rgba(99,85,232,0.04)}
.listitem.on{background:rgba(99,85,232,0.08);border-left:3px solid #6355e8}
.itemmeta{display:flex;align-items:center;gap:6px;margin-bottom:6px;flex-wrap:wrap}
.badge{font-size:10px;padding:2px 7px;border-radius:4px;font-weight:500}
.b-eye{background:rgba(96,165,250,0.15);color:#3b82f6}
.b-lifting{background:rgba(251,191,36,0.15);color:#d97706}
.b-nose{background:rgba(52,211,153,0.15);color:#059669}
.b-surgery{background:rgba(124,106,247,0.15);color:#7c6af7}
.b-concern{background:rgba(239,68,68,0.15);color:#ef4444}
.b-celeb{background:rgba(245,158,11,0.15);color:#d97706}
.itemtitle{font-size:13px;font-weight:500;line-height:1.4;margin-bottom:4px}
.itemkw{font-size:11px;color:#8888a8}
.itemdate{font-size:11px;color:#8888a8;margin-left:auto}
.detailpanel{overflow-y:auto;padding:24px;background:#f5f5f7}
.emptyst{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;color:#8888a8;gap:12px;font-size:14px}
.dtitle{font-size:20px;font-weight:700;line-height:1.4;margin-bottom:6px}
.dmeta{display:flex;gap:8px;align-items:center;margin-bottom:20px;flex-wrap:wrap}
.card{background:#fff;border:1px solid rgba(0,0,0,0.08);border-radius:12px;padding:18px;margin-bottom:12px;position:relative}
.cardlabel{font-size:10px;letter-spacing:2px;color:#8888a8;text-transform:uppercase;margin-bottom:10px}
.cardcontent{font-size:14px;line-height:1.8;color:#2d2d4e;white-space:pre-wrap}
.thumbbox{display:inline-block;background:linear-gradient(135deg,#6355e8,#5b4fe8);color:#fff;padding:10px 18px;border-radius:8px;font-size:15px;font-weight:700}
.tags{display:flex;flex-wrap:wrap;gap:6px}
.tag{background:rgba(99,85,232,0.1);border:1px solid rgba(99,85,232,0.2);color:#6355e8;padding:3px 9px;border-radius:4px;font-size:12px}
.ytlist{display:flex;flex-direction:column;gap:6px}
.ytitem{background:#f9f9fb;border:1px solid rgba(0,0,0,0.06);border-radius:8px;padding:10px 12px;display:flex;gap:10px}
.ytrank{font-size:11px;color:#8888a8;min-width:18px;padding-top:2px}
.ytinfo{flex:1;min-width:0}
.yttitle{font-size:13px;font-weight:500;margin-bottom:3px;line-height:1.4}
.yttitle a{color:#1a1a2e;text-decoration:none}
.yttitle a:hover{color:#6355e8}
.ytstats{font-size:11px;color:#8888a8;display:flex;gap:10px}
.ytviews{color:#059669}
.copybtn{background:rgba(99,85,232,0.1);border:1px solid rgba(99,85,232,0.2);color:#6355e8;padding:5px 12px;border-radius:6px;font-size:12px;font-family:'Noto Sans KR',sans-serif;cursor:pointer;float:right}
.overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:999;align-items:center;justify-content:center;flex-direction:column;gap:14px}
.overlay.show{display:flex}
.spinner{width:36px;height:36px;border:3px solid rgba(99,85,232,0.3);border-top-color:#6355e8;border-radius:50%;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.overlaytext{color:#6355e8;font-size:14px}
::-webkit-scrollbar{width:4px}
::-webkit-scrollbar-thumb{background:rgba(99,85,232,0.2);border-radius:2px}
</style>
</head>
<body>
<div class="topnav">
  <a href="/">📝 블로그</a>
  <a href="/youtube" class="on">🎬 유튜브 스크립트</a>
  <a href="/magazine">📰 매거진</a>
  <a href="/cardnews">🖼 카드뉴스</a>
  <a href="/threads">🧵 스레드</a>
</div>
<div class="header">
  <div class="logo">POP <span>유튜브 스크립트</span></div>
  <div style="display:flex;gap:8px">
    <select id="gencat" style="background:#f9f9fb;color:#1a1a2e;border:1px solid rgba(0,0,0,0.08);padding:8px 12px;border-radius:8px;font-family:'Noto Sans KR',sans-serif;font-size:13px">
      <option value="">전체 (10개)</option>
      <option value="eye">눈성형</option>
      <option value="lifting">리프팅</option>
      <option value="nose">코성형</option>
    </select>
    <button class="btn-gen" onclick="generate()">▶ 스크립트 생성</button>
  </div>
</div>
<div class="filterbar">
  <button class="tab on" onclick="filter('all',this)">전체</button>
  <button class="tab" onclick="filter('eye',this)">눈성형</button>
  <button class="tab" onclick="filter('lifting',this)">리프팅</button>
  <button class="tab" onclick="filter('nose',this)">코성형</button>
</div>
<div class="main">
  <div class="listpanel" id="listpanel"><div style="padding:20px;text-align:center;color:#8888a8;font-size:13px">불러오는 중...</div></div>
  <div class="detailpanel" id="detailpanel"><div class="emptyst"><span style="font-size:40px;opacity:.3">🎬</span><span>왼쪽에서 스크립트를 선택해주세요</span></div></div>
</div>
<div class="overlay" id="overlay"><div class="spinner"></div><div class="overlaytext" id="overlaytext">생성 중...</div></div>
<script>
let scripts=[],cf='all',cid=null;
const CL={eye:'눈성형',lifting:'리프팅',nose:'코성형'};
const KL={surgery:'수술명',concern:'고민형',celeb:'연예인'};
async function load(){
  const r=await fetch('/api/yt/scripts');
  scripts=await r.json();
  render();
}
function filter(c,btn){
  cf=c;
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('on'));
  btn.classList.add('on');
  render();
}
function render(){
  const list=cf==='all'?scripts:scripts.filter(s=>s.category===cf);
  const p=document.getElementById('listpanel');
  if(!list.length){p.innerHTML='<div style="padding:20px;text-align:center;color:#8888a8;font-size:13px">스크립트가 없습니다</div>';return;}
  p.innerHTML=list.map(s=>`
    <div class="listitem ${s.id===cid?'on':''}" onclick="detail('${s.id}')">
      <div class="itemmeta">
        <span class="badge b-${s.category}">${CL[s.category]}</span>
        <span class="badge b-${s.keyword_type}">${KL[s.keyword_type]}</span>
        <span class="itemdate">${s.date}</span>
      </div>
      <div class="itemtitle">${s.script&&s.script.titles&&s.script.titles[0]?s.script.titles[0]:s.keyword}</div>
      <div class="itemkw">키워드: ${s.keyword}</div>
    </div>`).join('');
}
function detail(id){
  cid=id;render();
  const s=scripts.find(x=>x.id===id);
  if(!s)return;
  const sc=s.script;
  const top=(s.youtube_top10||[]).slice(0,10);
  const titles=(sc.titles||[]);
  const mainSubs=(sc.main&&sc.main.subtitles)||[];
  document.getElementById('detailpanel').innerHTML=`
    <div class="dtitle">${titles[0]||''}</div>
    <div class="dmeta">
      <span class="badge b-${s.category}">${CL[s.category]}</span>
      <span class="badge b-${s.keyword_type}">${KL[s.keyword_type]}</span>
      <span style="font-size:12px;color:#8888a8">키워드: ${s.keyword}</span>
      <span style="font-size:12px;color:#8888a8">${s.date}</span>
    </div>
    <div class="card"><div class="cardlabel">제목 후보 (SEO/GEO)</div><div class="cardcontent">${titles.map((t,i)=>`${i+1}. ${t}`).join('<br>')}</div></div>
    <div class="card"><div class="cardlabel">썸네일 문구</div><div class="thumbbox">${sc.thumbnail_main||''}</div><div style="font-size:12px;color:#8888a8;margin-top:4px">${sc.thumbnail_sub||''}</div></div>
    <div class="card"><div class="cardlabel">트렌드 분석</div><div class="cardcontent">${sc.trend_analysis||''}</div></div>
    <div class="card">
      <button class="copybtn" onclick="copy()">복사</button>
      <div class="cardlabel">훅 (0~4초)</div>
      <div class="cardcontent" id="scripttext">${(sc.hook&&sc.hook.narration)||''}</div>
      <div style="font-size:12px;color:#8888a8;margin-top:4px">자막: ${(sc.hook&&sc.hook.subtitle)||''}</div>
    </div>
    <div class="card">
      <div class="cardlabel">핵심 (4~22초)</div>
      <div class="cardcontent">${(sc.main&&sc.main.narration)||''}</div>
      <div style="font-size:12px;color:#8888a8;margin-top:4px">자막: ${mainSubs.join(' / ')}</div>
    </div>
    <div class="card">
      <div class="cardlabel">CTA (22~30초)</div>
      <div class="cardcontent">${(sc.cta&&sc.cta.narration)||''}</div>
      <div style="font-size:12px;color:#8888a8;margin-top:4px">자막: ${(sc.cta&&sc.cta.subtitle)||''}</div>
    </div>
    <div class="card"><div class="cardlabel">추천 해시태그</div><div class="tags">${(sc.hashtags||[]).map(t=>'<span class="tag">'+(t.startsWith('#')?t:'#'+t)+'</span>').join('')}</div></div>
    <div class="card"><div class="cardlabel">유튜브 Top 10</div><div class="ytlist">${top.map((v,i)=>`
      <div class="ytitem"><div class="ytrank">${i+1}</div><div class="ytinfo">
        <div class="yttitle"><a href="${v.url}" target="_blank">${v.title}</a></div>
        <div class="ytstats"><span class="ytviews">👁 ${Number(v.view_count||0).toLocaleString()}회</span><span>💬 ${Number(v.comment_count||0).toLocaleString()}</span><span>${v.channel}</span></div>
      </div></div>`).join('')}</div></div>`;
}
function copy(){
  const s=scripts.find(x=>x.id===cid);
  if(!s)return;
  const sc=s.script;
  const full=[
    '훅: '+((sc.hook&&sc.hook.narration)||''),
    '핵심: '+((sc.main&&sc.main.narration)||''),
    'CTA: '+((sc.cta&&sc.cta.narration)||'')
  ].join('\\n');
  navigator.clipboard.writeText(full).then(()=>alert('복사 완료!'));
}
async function generate(){
  const cat=document.getElementById('gencat').value;
  const btn=document.querySelector('.btn-gen');
  const ov=document.getElementById('overlay');
  btn.disabled=true;
  ov.classList.add('show');
  document.getElementById('overlaytext').textContent=cat?CL[cat]+' 생성 중...':'전체 생성 중...';
  try{
    const r=await fetch('/api/yt/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({category:cat})});
    const d=await r.json();
    if(d.success){await load();if(scripts.length>0)detail(scripts[0].id);}
    else alert('실패: '+d.error);
  }catch(e){alert('오류: '+e.message);}
  finally{btn.disabled=false;ov.classList.remove('show');}
}
load();
</script>
</body>
</html>"""


def load_yt_scripts():
    import json as _json
    from pathlib import Path as _Path
    scripts = []
    out = _Path(YT_OUTPUT)
    if not out.exists():
        return scripts
    # 루트 + 날짜 서브폴더 모두 재귀 스캔
    all_files = sorted(out.rglob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    for f in all_files:
        try:
            data = _json.loads(f.read_text(encoding="utf-8"))
            data["id"] = f.stem
            scripts.append(data)
        except:
            pass
    return scripts


@app.route("/youtube")
def youtube_page():
    return render_template_string(YT_HTML)


@app.route("/api/yt/scripts")
def api_yt_scripts():
    return jsonify(load_yt_scripts())


@app.route("/api/yt/generate", methods=["POST"])
def api_yt_generate():
    import subprocess as _sp
    try:
        cat = (request.json or {}).get("category") or ""
        cmd = ["python", "youtube_script.py"]
        if cat:
            cmd += ["--category", cat]
        # 10편 병렬 생성 - 넉넉하게 10분
        result = _sp.run(cmd, cwd=YT_DIR, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            return jsonify({"success": False, "error": result.stderr[-2000:]})
        return jsonify({"success": True})
    except _sp.TimeoutExpired:
        return jsonify({"success": False, "error": "timeout - 생성 시간 초과 (10분)"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


MAG_HTML = r"""
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>팝성형외과 / 매거진</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI','Noto Sans KR',sans-serif;background:#f0f2f5;color:#333}
.nav{background:#1a1a2e;border-bottom:2px solid rgba(167,139,250,.2);padding:0 24px;display:flex;position:sticky;top:0;z-index:999}
.nav a{padding:13px 22px;font-size:13px;font-weight:500;color:#a0a0c0;text-decoration:none;border-bottom:3px solid transparent;margin-bottom:-2px}
.nav a.on{color:#a78bfa;border-bottom-color:#a78bfa}
.header{background:linear-gradient(135deg,#1a1a2e,#16213e);color:#fff;padding:18px 30px;display:flex;justify-content:space-between;align-items:center}
.header h1{font-size:19px;font-weight:600}
.bar{max-width:1280px;margin:0 auto;padding:18px 24px 0;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.bar select{padding:8px 12px;border:1px solid #ddd;border-radius:8px;font-size:13px;background:#fff}
.chip{padding:7px 16px;border-radius:20px;border:1px solid #ddd;background:#fff;cursor:pointer;font-size:12px;color:#666}
.chip.on{background:#1a1a2e;color:#fff;border-color:#1a1a2e}
.pchip{padding:7px 14px;border-radius:20px;border:1px solid #ddd;background:#fff;cursor:pointer;font-size:12px;color:#666}
.pchip.on{background:#2ecc71;color:#fff;border-color:#2ecc71}
.pbadge{display:inline-block;padding:2px 9px;border-radius:20px;font-size:10px;font-weight:600;margin-left:6px}
.pbadge.pub{background:#e8fef0;color:#2ecc71}
.pbadge.pend{background:#fff8e8;color:#f39c12}
.wrap{max-width:1280px;margin:0 auto;padding:18px 24px 60px;display:grid;grid-template-columns:340px 1fr;gap:18px}
.list{background:#fff;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.06);max-height:78vh;overflow:auto}
.item{padding:14px 16px;border-bottom:1px solid #f0f0f0;cursor:pointer}
.item:hover{background:#fafafa}
.item.on{background:#f3efff;border-left:3px solid #a78bfa}
.item .m{display:flex;gap:6px;align-items:center;margin-bottom:6px}
.badge{display:inline-block;padding:2px 9px;border-radius:20px;font-size:11px;font-weight:600}
.b-눈성형{background:#e8f0fe;color:#4f8ef7}.b-리프팅{background:#fff0e8;color:#f7934f}.b-코성형{background:#e8faf3;color:#4fd19e}
.item .t{font-size:13px;font-weight:600;color:#222;line-height:1.4}
.item .k{font-size:11px;color:#999;margin-top:3px}
.idate{font-size:11px;color:#bbb;margin-left:auto}
.detail{background:#fff;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.06);display:flex;flex-direction:column;min-height:78vh}
.toolbar{padding:14px 18px;border-bottom:1px solid #eee;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.btn{padding:9px 16px;border-radius:8px;border:1px solid #ddd;background:#fff;font-size:13px;font-weight:600;cursor:pointer;color:#333}
.btn.p{background:#1a1a2e;color:#fff;border-color:#1a1a2e}
.btn:disabled{opacity:.45;cursor:not-allowed}
.metapanel{padding:0 14px 6px}
.imgset{display:flex;gap:8px;align-items:center;padding:10px 14px;border-bottom:1px solid #f1f1f4}
.imgset-label{font-size:12px;font-weight:700;color:#6355e8;white-space:nowrap}
.imgset input{flex:1;border:1px solid #ddd;border-radius:8px;padding:9px 12px;font-size:12.5px;font-family:inherit}
.imgset input:focus{outline:2px solid #c9b8ff;border-color:#a78bfa}
.metahead{font-size:11px;font-weight:700;letter-spacing:.05em;color:#6355e8;background:#f3efff;border:1px solid #e3dcff;border-radius:8px;padding:8px 12px;margin:0 0 8px}
.metarow{display:grid;grid-template-columns:120px 1fr auto;gap:10px;align-items:center;padding:7px 4px;border-bottom:1px solid #f1f1f4;font-size:12.5px}
.metarow:last-child{border-bottom:none}
.mlabel{color:#888;font-weight:600}
.mval{color:#222;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mcopy{padding:5px 12px;border-radius:14px;border:1px solid #ddd;background:#fff;font-size:11px;cursor:pointer;color:#555;white-space:nowrap}
.mcopy:hover{background:#6355e8;color:#fff;border-color:#6355e8}
.frame{flex:1;padding:14px}
iframe{width:100%;height:100%;min-height:620px;border:1px solid #eee;border-radius:10px;background:#fff}
.empty{display:flex;align-items:center;justify-content:center;height:620px;color:#bbb;font-size:14px;gap:10px;flex-direction:column}
.note{max-width:1280px;margin:0 auto;padding:0 24px 40px;color:#9a8d80;font-size:12px;line-height:1.7}
@media(max-width:860px){.wrap{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="nav">
  <a href="/">📝 블로그</a>
  <a href="/youtube">🎬 유튜브 스크립트</a>
  <a href="/magazine" class="on">📰 매거진</a>
  <a href="/cardnews">🖼 카드뉴스</a>
  <a href="/threads">🧵 스레드</a>
</div>
<div class="header"><h1>📰 팝성형외과 매거진</h1><span style="font-size:12px;color:#aaa">발행용 HTML / 복사하여 붙여넣기</span></div>

<div class="bar">
  <select id="dateSel" onchange="render()"></select>
  <span style="width:1px;height:20px;background:#ddd"></span>
  <button class="chip on" data-c="all" onclick="setCat(this)">전체</button>
  <button class="chip" data-c="눈성형" onclick="setCat(this)">눈성형</button>
  <button class="chip" data-c="리프팅" onclick="setCat(this)">리프팅</button>
  <button class="chip" data-c="코성형" onclick="setCat(this)">코성형</button>
  <span style="width:1px;height:20px;background:#ddd"></span>
  <button class="pchip on" data-p="all" onclick="setPub(this)">전체</button>
  <button class="pchip" data-p="pend" onclick="setPub(this)">미발행</button>
  <button class="pchip" data-p="pub" onclick="setPub(this)">발행완료</button>
  <span id="pubCount" style="font-size:12px;color:#2ecc71;font-weight:600;margin-left:4px"></span>
  <span style="flex:1"></span>
  <select id="genCat" style="padding:8px 12px;border:1px solid #ddd;border-radius:8px;font-size:13px;background:#fff">
    <option value="">전체 (10개)</option>
    <option value="눈성형">눈성형</option>
    <option value="리프팅">리프팅</option>
    <option value="코성형">코성형</option>
  </select>
  <button class="chip" style="background:#6355e8;color:#fff;border-color:#6355e8;font-weight:600" onclick="genMag(this)">▶ 매거진 생성</button>
  <button class="chip" id="btnDay" style="background:#1a1a2e;color:#fff;border-color:#1a1a2e;font-weight:700" onclick="genDay(this)" title="눈5/리프팅5/코5 = 15편을 순차 생성합니다 (몇 분 소요)">▶ 하루 15편 생성</button>
</div>

<div class="wrap">
  <div class="list" id="list"></div>
  <div class="detail">
    <div class="toolbar">
      <button class="btn p" id="btnRich" onclick="copyRich()" disabled>📋 본문 복사 (서식)</button>
      <button class="btn" id="btnSrc" onclick="copySrc()" disabled>&lt;/&gt; HTML 소스 복사</button>
      <button class="btn" id="btnPub" onclick="togglePub()" disabled>⬜ 미발행</button>
      <span id="curTitle" style="font-size:12px;color:#999;margin-left:auto"></span>
    </div>
    <div class="imgset">
      <span class="imgset-label">사람 이미지 URL</span>
      <input type="text" id="imgUrl" placeholder="Higgsfield 이미지 URL 붙여넣기 (https://...) / 비우고 저장하면 제거" disabled>
      <button class="btn p" id="btnImg" onclick="saveImage()" disabled>이미지 저장</button>
    </div>
    <div id="metaPanel" class="metapanel"></div>
    <div class="frame">
      <div class="empty" id="empty"><span style="font-size:40px;opacity:.3">📰</span><span>왼쪽에서 글을 선택하면 매거진 미리보기가 나타나요</span></div>
      <iframe id="frame" title="매거진 미리보기" style="display:none"></iframe>
    </div>
  </div>
</div>
<div class="note">※ ‘본문 복사(서식)'은 네이버/티스토리 등 에디터에 붙여넣으면 제목/문단/FAQ가 서식째 들어가요(일부 에디터는 배경 스타일/인포그래픽을 단순화할 수 있어요). ‘HTML 소스 복사'는 HTML 편집 모드/자체 CMS용 전체 소스예요. 카드 이미지는 블로그 탭의 카드 복사 버튼과 함께 쓰면 됩니다.<br>※ 본 산출물은 정보 제공용이며, 전후사진/효과 표현 등은 게시 전 의료광고 심의를 거쳐야 합니다.</div>

<script>
let DATA={dates:[],posts_by_date:{}}, CAT='all', PUB='all', CURID=null, CURHTML='', CURPOST=null, CURHERO='', CURMETA=null, CURBODY='', CURHEROISPHOTO=false;

async function boot(){
  const r=await fetch('/api/mag/data'); DATA=await r.json();
  const sel=document.getElementById('dateSel');
  sel.innerHTML=(DATA.dates||[]).map(d=>`<option value="${d}">${d.slice(0,4)}.${d.slice(4,6)}.${d.slice(6,8)}</option>`).join('');
  render();
}
function setCat(b){CAT=b.dataset.c;document.querySelectorAll('.chip').forEach(c=>c.classList.remove('on'));b.classList.add('on');render();}
function setPub(b){PUB=b.dataset.p;document.querySelectorAll('.pchip').forEach(c=>c.classList.remove('on'));b.classList.add('on');render();}
function curDate(){return document.getElementById('dateSel').value || (DATA.dates&&DATA.dates[0]);}
function posts(){
  let p=(DATA.posts_by_date[curDate()]||[]);
  if(CAT!=='all') p=p.filter(x=>x.category===CAT);
  if(PUB==='pub') p=p.filter(x=>x.published);
  else if(PUB==='pend') p=p.filter(x=>!x.published);
  return p;
}
function updateCount(){
  let p=(DATA.posts_by_date[curDate()]||[]); if(CAT!=='all') p=p.filter(x=>x.category===CAT);
  const pub=p.filter(x=>x.published).length;
  const el=document.getElementById('pubCount'); if(el) el.textContent='발행완료 '+pub+' / 전체 '+p.length;
}
function render(){
  const list=posts();
  updateCount();
  const el=document.getElementById('list');
  if(!list.length){el.innerHTML='<div class="empty" style="height:200px">해당 글이 없어요</div>';return;}
  el.innerHTML=list.map(p=>`
    <div class="item ${p.post_id===CURID?'on':''}" onclick="pick('${p.post_id}')">
      <div class="m"><span class="badge b-${p.category}">${p.category||'-'}</span><span class="pbadge ${p.published?'pub':'pend'}">${p.published?'발행완료':'미발행'}</span><span class="idate">${(p.date||'').slice(4,6)}/${(p.date||'').slice(6,8)}</span></div>
      <div class="t">${esc(p.title||p.keyword||'(제목 없음)')}</div>
      <div class="k">키워드: ${esc(p.keyword||'-')}</div>
    </div>`).join('');
}
function findPost(id){for(const d in DATA.posts_by_date){const f=DATA.posts_by_date[d].find(p=>p.post_id===id);if(f)return f;}return null;}
async function pick(id){
  CURID=id;render();
  const p=findPost(id);if(!p)return;
  CURPOST=p;
  let cards=[];
  try{const r=await fetch('/api/mag/cards?filename='+encodeURIComponent(p.filename)+'&date='+p.date);cards=await r.json();}catch(e){}
  const isHtml = (p.content||'').trim().startsWith('<') || (p.content||'').includes('</');
  let cat, title, kw, desc;

  if (isHtml) {
    // HTML 콘텐츠 - 그대로 iframe에 표시
    cat = p.category || '';
    title = p.title || p.keyword || '';
    kw = p.keyword || '';
    desc = title;
    CURHERO = p.hero || '';
    CURHEROISPHOTO = false;
    CURMETA = {
      title: title, slug: '', summary: '',
      category: cat, visible: '공개', publishAt: '',
      seokw: kw, seodesc: desc
    };
    CURBODY = p.content || '';
    CURHTML = p.content || '';
  } else {
    // 텍스트 파싱 방식
    const P = parsePost(p.content);
    cat = p.category || P.meta.category || '';
    title = p.title || P.meta.title || p.keyword || '';
    kw = P.meta.seokw || p.keyword || '';
    desc = P.meta.seodesc || (P.intro || title).slice(0, 90);
    const photo = (P.meta.image && /^https?:\/\//.test(P.meta.image)) ? P.meta.image : (p.hero || '');
    CURHERO = photo || uri(hero(cat, title));
    CURHEROISPHOTO = !!photo;
    CURMETA = {
      title: title, slug: P.meta.slug || '', summary: P.meta.summary || '',
      category: cat, visible: P.meta.visible || '공개', publishAt: P.meta.publishAt || '',
      seokw: kw, seodesc: desc
    };
    CURBODY = bodyInner(P, cat, title, cards || [], P.meta.keyword || p.keyword || title);
    CURHTML = buildFull(P, cat, title, kw, desc, CURHERO, CURBODY);
  }

  document.getElementById('empty').style.display='none';
  const fr=document.getElementById('frame');fr.style.display='block';fr.srcdoc=CURHTML;
  renderMeta(CURMETA);
  document.getElementById('btnRich').disabled=false;document.getElementById('btnSrc').disabled=false;
  const iu=document.getElementById('imgUrl'); iu.disabled=false; iu.value=(P.meta.image||''); document.getElementById('btnImg').disabled=false;
  setPubBtn();
  document.getElementById('curTitle').textContent=title;
}
async function saveImage(){
  if(!CURPOST)return;
  const url=document.getElementById('imgUrl').value.trim();
  const b=document.getElementById('btnImg'); const old=b.textContent; b.disabled=true; b.textContent='저장 중...';
  try{
    const r=await fetch('/api/mag/set_image',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({date:CURPOST.date,filename:CURPOST.filename,url:url})});
    const d=await r.json();
    if(d.ok){ const id=CURID; await boot(); await pick(id); toast(url?'사람 이미지 적용 완료':'이미지 제거 완료'); }
    else { alert('저장 실패: '+(d.error||'')); }
  }catch(e){ alert('오류: '+e.message); }
  finally{ b.disabled=false; b.textContent=old; }
}
function renderMeta(m){
  const rows=[
    ['제목 *', m.title],
    ['슬러그 (URL)', m.slug],
    ['요약 (리스트 노출용)', m.summary],
    ['카테고리', m.category],
    ['노출 여부 *', m.visible],
    ['게시 일시', m.publishAt || '(직접 지정)'],
    ['SEO 키워드', m.seokw],
    ['SEO 설명', m.seodesc]
  ];
  let html='<div class="metahead">📋 메타 - 폼 항목에 따로 입력 (본문 복사에는 포함되지 않아요)</div>';
  html+=rows.map(r=>'<div class="metarow"><div class="mlabel">'+esc(r[0])+'</div><div class="mval" title="'+esc(r[1]||'')+'">'+esc(r[1]||'')+'</div><button class="mcopy" onclick="copyField(this)">복사</button></div>').join('');
  html+='<div class="metarow"><div class="mlabel">대표 썸네일 / OG</div><div class="mval"><img src="'+CURHERO+'" style="height:50px;border-radius:6px;border:1px solid #eee;vertical-align:middle"></div><button class="mcopy" onclick="dlThumb()">PNG 다운로드</button></div>';
  document.getElementById('metaPanel').innerHTML=html;
}
function copyField(btn){
  const v=btn.parentNode.querySelector('.mval').getAttribute('title') || btn.parentNode.querySelector('.mval').innerText || '';
  navigator.clipboard.writeText(v).then(()=>{const o=btn.textContent;btn.textContent='복사됨';btn.style.background='#2ecc71';btn.style.color='#fff';setTimeout(()=>{btn.textContent=o;btn.style.background='';btn.style.color='';},1200);}).catch(()=>alert('복사 실패'));
}
function dlThumb(){
  if(CURHEROISPHOTO){ const a=document.createElement('a');a.href=CURHERO;a.download='thumbnail';a.target='_blank';a.click();return; }
  const img=new Image();
  img.onload=()=>{
    const c=document.createElement('canvas');c.width=1200;c.height=Math.round(1200*405/720);
    c.getContext('2d').drawImage(img,0,0,c.width,c.height);
    try{ c.toBlob(b=>{const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='thumbnail.png';a.click();URL.revokeObjectURL(a.href);},'image/png'); }
    catch(e){ const a=document.createElement('a');a.href=CURHERO;a.download='thumbnail.svg';a.click(); }
  };
  img.onerror=()=>{const a=document.createElement('a');a.href=CURHERO;a.download='thumbnail.svg';a.click();};
  img.src=CURHERO;
}
function setPubBtn(){
  const b=document.getElementById('btnPub');
  if(!CURPOST){b.disabled=true;return;}
  b.disabled=false;
  b.textContent=CURPOST.published?'✅ 발행완료':'⬜ 미발행';
  b.style.background=CURPOST.published?'#e8fef0':'#fff';
  b.style.color=CURPOST.published?'#2ecc71':'#333';
  b.style.borderColor=CURPOST.published?'#2ecc71':'#ddd';
}
async function togglePub(){
  if(!CURPOST)return;
  try{
    const r=await fetch('/api/toggle_published',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({post_id:CURPOST.post_id})});
    const d=await r.json();
    CURPOST.published=d.published;
    for(const dt in DATA.posts_by_date){const f=DATA.posts_by_date[dt].find(x=>x.post_id===CURPOST.post_id);if(f)f.published=d.published;}
    setPubBtn();render();
    toast(d.published?'발행완료로 표시했어요':'미발행으로 되돌렸어요');
  }catch(e){alert('상태 변경 실패: '+e.message);}
}

/* ---------- 매거진 HTML 빌더 ---------- */
function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function uri(svg){return 'data:image/svg+xml;base64,'+btoa(unescape(encodeURIComponent(svg)));}
function wrapTitle(title,max){
  const words=String(title||'').split(' ');const lines=[];let cur='';
  words.forEach(w=>{ if((cur+' '+w).trim().length>max){ if(cur)lines.push(cur); cur=w; } else { cur=(cur?cur+' ':'')+w; } });
  if(cur)lines.push(cur); return lines.slice(0,3);
}
function hero(cat,title){
  const lines=wrapTitle(title,16);
  const tspans=lines.map((l,i)=>'<text x="56" y="'+(196+i*44)+'" font-family="Georgia,serif" font-size="33" font-weight="700" fill="#1a1a1a">'+esc(l)+'</text>').join('');
  return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 405">'
    +'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fdf8f5"/><stop offset="1" stop-color="#f3e7dd"/></linearGradient></defs>'
    +'<rect width="720" height="405" fill="url(#g)"/><g stroke="#e7d8cc" stroke-width="1" opacity=".55"><line x1="0" y1="135" x2="720" y2="135"/><line x1="0" y1="270" x2="720" y2="270"/></g>'
    +'<text x="56" y="150" font-family="Georgia,serif" font-size="13" letter-spacing="4" fill="#b07d62" font-weight="700">'+esc((cat||'').toUpperCase())+' / 팝성형외과</text>'
    +tspans
    +'<line x1="56" y1="350" x2="300" y2="350" stroke="#d4a882" stroke-width="2"/></svg>';
}
function checklistSVG(heading,items){
  items=(items||[]).slice(0,4);
  const rows=items.map((t,i)=>{const y=124+i*52;return '<circle cx="48" cy="'+(y-5)+'" r="10" fill="#b07d62"/><path d="M43 '+(y-5)+' l4 4 l6 -8" stroke="#fff" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/><text x="70" y="'+y+'" font-family="\'Noto Sans KR\',sans-serif" font-size="15" fill="#3a3a3a">'+esc(t)+'</text>';}).join('');
  const h=120+items.length*52;
  return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 '+h+'"><rect width="720" height="'+h+'" fill="#fdf8f5"/><text x="40" y="60" font-family="Georgia,\'Noto Serif KR\',serif" font-size="20" font-weight="700" fill="#1a1a1a">'+esc(heading)+'</text>'+rows+'</svg>';
}
function compareSVG(c){
  const L=(c.litems||[]).slice(0,5), R=(c.ritems||[]).slice(0,5);
  const n=Math.max(L.length,R.length,1), h=104+n*40;
  const li=L.map((t,i)=>'<text x="40" y="'+(104+i*40)+'" font-family="\'Noto Sans KR\',sans-serif" font-size="14" fill="#3a3a3a">✓ '+esc(t)+'</text>').join('');
  const ri=R.map((t,i)=>'<text x="392" y="'+(104+i*40)+'" font-family="\'Noto Sans KR\',sans-serif" font-size="14" fill="#5a4d42">/ '+esc(t)+'</text>').join('');
  return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 '+h+'"><rect width="720" height="'+h+'" fill="#fff"/><rect width="360" height="'+h+'" fill="#fdf8f5"/><line x1="360" y1="28" x2="360" y2="'+(h-22)+'" stroke="#ece6e0"/><text x="40" y="58" font-family="\'Noto Sans KR\',sans-serif" font-size="12" font-weight="700" letter-spacing="1" fill="#b07d62">'+esc(c.lt||'')+'</text><text x="392" y="58" font-family="\'Noto Sans KR\',sans-serif" font-size="12" font-weight="700" letter-spacing="1" fill="#8a7b6e">'+esc(c.rt||'')+'</text>'+li+ri+'</svg>';
}
function dataCardSVG(d){
  d=(d||[]).slice(0,3);const n=Math.max(d.length,1);const gap=16;const cw=(720-32-gap*(n-1))/n;
  const cards=d.map((it,i)=>{const x=16+i*(cw+gap);return '<rect x="'+x+'" y="28" width="'+cw+'" height="150" rx="10" fill="#fdf8f5" stroke="#ece6e0"/><text x="'+(x+18)+'" y="72" font-family="\'Noto Sans KR\',sans-serif" font-size="12" font-weight="700" fill="#b07d62">'+esc(it.label)+'</text><text x="'+(x+18)+'" y="124" font-family="Georgia,serif" font-size="25" font-weight="700" fill="#1a1a1a">'+esc(it.val)+'</text>';}).join('');
  return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 206"><rect width="720" height="206" fill="#fff"/>'+cards+'</svg>';
}
function autoPoints(bodyArr){
  const text=(bodyArr||[]).join(' ');
  let parts=text.split(/(?<=[.!?])\s+/).map(x=>x.trim()).filter(x=>x.length>4);
  parts=parts.slice(0,3).map(x=>x.length>30?x.slice(0,29)+'...':x);
  return parts.length?parts:['핵심 포인트'];
}
function parsePost(content){
  const lines=(content||'').split('\n');
  let intro=[],sections=[],faq=[],figs=[],cur=null,q=null,compare=null,data=null;
  const meta={};
  const HK={'카테고리':'category','키워드':'keyword','제목':'title','슬러그':'slug','요약':'summary','SEO키워드':'seokw','SEO 키워드':'seokw','SEO설명':'seodesc','SEO 설명':'seodesc','노출여부':'visible','노출 여부':'visible','게시일시':'publishAt','게시 일시':'publishAt','이미지':'image','대표이미지':'image','히어로':'image','생성일':'createdAt'};
  for(let raw of lines){
    const t=raw.trim();
    if(!t||/^={3,}$/.test(t))continue;
    const ci=t.indexOf(':');
    if(ci>0 && HK[t.slice(0,ci).trim()]!==undefined){ meta[HK[t.slice(0,ci).trim()]]=t.slice(ci+1).trim(); continue; }
    if(t.indexOf('## ')===0){cur={title:t.substring(3),body:[],points:null};sections.push(cur);continue;}
    if(t.indexOf('[인포그래픽]')===0){const p=t.replace('[인포그래픽]','').split('|').map(x=>x.trim()).filter(Boolean);if(p.length>=2)figs.push({heading:p[0],items:p.slice(1)});continue;}
    if(t.indexOf('[핵심]')===0){const p=t.replace('[핵심]','').split('|').map(x=>x.trim()).filter(Boolean);if(cur&&p.length)cur.points=p;continue;}
    if(t.indexOf('[비교]')===0){const p=t.replace('[비교]','').split('|').map(x=>x.trim());if(p.length>=4)compare={lt:p[0],litems:p[1].split(';').map(x=>x.trim()).filter(Boolean),rt:p[2],ritems:p[3].split(';').map(x=>x.trim()).filter(Boolean)};continue;}
    if(t.indexOf('[데이터]')===0){const p=t.replace('[데이터]','').split('|').map(x=>x.trim()).filter(Boolean);const arr=[];for(let k=0;k+1<p.length;k+=2)arr.push({label:p[k],val:p[k+1]});if(arr.length)data=arr;continue;}
    const mq=t.match(/^Q[0-9]*\.?\s*(.*)$/),ma=t.match(/^A[0-9]*\.?\s*(.*)$/);
    if(mq){q={q:mq[1],a:''};faq.push(q);continue;}
    if(ma){if(q)q.a=(q.a?q.a+' ':'')+ma[1];continue;}
    if(cur)cur.body.push(t);else intro.push(t);
  }
  return {meta:meta,intro:intro.join(' '),sections:sections,faq:faq,figs:figs,compare:compare,data:data};
}
const CSS="*{box-sizing:border-box}body{margin:0;background:#f6f1ec}.mag-wrap{font-family:'Noto Sans KR',sans-serif;color:#1a1a1a;max-width:720px;margin:0 auto;padding:48px 20px 60px;line-height:1.85;background:#fff}.mag-tag{display:inline-block;font-size:11px;font-weight:600;letter-spacing:.12em;color:#b07d62;text-transform:uppercase;margin-bottom:20px}.mag-title{font-family:'Noto Serif KR',Georgia,serif;font-size:28px;font-weight:700;line-height:1.4;color:#111;margin:0 0 24px}.mag-hero{width:100%;border-radius:12px;display:block}figure{margin:0 0 40px}figcaption{font-size:12px;color:#9a8d80;margin-top:8px;text-align:center}.mag-intro{font-size:15px;color:#444;background:#fdf8f5;border-left:3px solid #d4a882;padding:20px 24px;border-radius:0 8px 8px 0;margin-bottom:48px}.mag-num{font-size:11px;font-weight:700;letter-spacing:.15em;color:#c9a882;text-transform:uppercase;margin-bottom:8px}.mag-section-title{font-family:'Noto Serif KR',Georgia,serif;font-size:20px;font-weight:700;color:#111;line-height:1.45;margin:0 0 16px}.mag-p{font-size:15px;color:#3a3a3a;margin-bottom:16px}.mag-fig{width:100%;border-radius:10px;display:block;border:1px solid #f0e8e0}.mag-divider{border:none;border-top:1px solid #ece6e0;margin:44px 0}.mag-faq{margin-top:48px;border-top:2px solid #111;padding-top:32px}.mag-faq-title{font-size:12px;font-weight:700;letter-spacing:.12em;color:#888;text-transform:uppercase;margin-bottom:24px}.mag-faq-item{padding:20px 0;border-bottom:1px solid #ece6e0}.mag-faq-q{font-size:15px;font-weight:700;color:#111;margin:0 0 10px}.mag-faq-a{font-size:14px;color:#555;line-height:1.8;margin:0}.qa{color:#b07d62;font-weight:700;margin-right:6px}.mag-cta-wrap{text-align:center;margin:40px 0 8px}.mag-cta{display:inline-block;background:#b07d62;color:#fff;text-decoration:none;font-weight:700;padding:15px 30px;border-radius:999px;font-size:15px;box-shadow:0 4px 14px rgba(176,125,98,.35)}.mag-cta:hover{background:#9a6a52}.mag-closing{background:#1a1a1a;color:#fff;border-radius:12px;padding:36px 32px;margin-top:48px;text-align:center}.mag-closing-title{font-family:'Noto Serif KR',Georgia,serif;font-size:18px;font-weight:700;margin:0 0 12px;line-height:1.5}.mag-closing-body{font-size:13px;color:#aaa;line-height:1.8;margin:0}";
function bodyInner(P,cat,title,cards,kw){
  cards=cards||[];
  let html='';
  if(P.intro) html+='<div class="mag-intro">'+esc(P.intro)+'</div>';
  // ① 핵심 요약 인포그래픽
  let fig=P.figs[0];
  if(!fig && P.sections.length) fig={heading:'이 글의 핵심',items:P.sections.map(s=>s.title)};
  if(fig){const svg=uri(checklistSVG(fig.heading,fig.items));
    html+='<figure><img class="mag-fig" src="'+svg+'" alt="'+esc(title+' 핵심 요약 인포그래픽')+'" loading="lazy"><figcaption>'+esc(fig.heading)+'</figcaption></figure>';}
  // ② 섹션 + 섹션별 인포그래픽(모델이 준 [핵심] 우선, 없으면 본문에서 자동 생성)
  P.sections.forEach((s,i)=>{
    const items=(s.points&&s.points.length)?s.points:autoPoints(s.body);
    const svg=uri(checklistSVG(s.title,items));
    const f='<figure><img class="mag-fig" src="'+svg+'" alt="'+esc(title+' '+s.title+' 인포그래픽')+'" loading="lazy"><figcaption>'+esc(s.title)+'</figcaption></figure>';
    html+='<hr class="mag-divider"><section><p class="mag-num">'+String(i+1).padStart(2,'0')+'</p><h2 class="mag-section-title">'+esc(s.title)+'</h2>'+s.body.map(p=>'<p class="mag-p">'+esc(p)+'</p>').join('')+f+'</section>';
  });
  // ③ 비교 인포그래픽
  if(P.compare){const svg=uri(compareSVG(P.compare));
    html+='<hr class="mag-divider"><figure><img class="mag-fig" src="'+svg+'" alt="'+esc(title+' '+(P.compare.lt||'')+' '+(P.compare.rt||'')+' 비교 인포그래픽')+'" loading="lazy"><figcaption>'+esc((P.compare.lt||'')+' vs '+(P.compare.rt||''))+'</figcaption></figure>';}
  // ④ 데이터 카드 인포그래픽
  if(P.data){const svg=uri(dataCardSVG(P.data));
    html+='<hr class="mag-divider"><figure><img class="mag-fig" src="'+svg+'" alt="'+esc(title+' 핵심 데이터 인포그래픽')+'" loading="lazy"><figcaption>핵심 수치</figcaption></figure>';}
  // ⑤ 추가 사람 사진(있으면)
  cards.forEach((c,j)=>{ html+='<hr class="mag-divider"><figure><img class="mag-fig" src="'+esc(c)+'" alt="'+esc(cat+' '+title+' 관련 이미지 '+(j+1))+'" loading="lazy"></figure>'; });
  if(P.faq.length){
    html+='<section class="mag-faq"><p class="mag-faq-title">자주 묻는 질문</p>'
      +P.faq.map(f=>'<div class="mag-faq-item"><p class="mag-faq-q"><span class="qa">Q.</span>'+esc(f.q)+'</p><p class="mag-faq-a"><span class="qa">A.</span>'+esc(f.a)+'</p></div>').join('')
      +'</section>';
  }
  const ctaLabel=((kw||title||'').trim()||'더')+' 보러 가기';
  html+='<div class="mag-cta-wrap"><a class="mag-cta" href="https://pop-ps.com/main" target="_blank" rel="noopener">'+esc(ctaLabel)+' -></a></div>';
  html+='<div class="mag-closing"><p class="mag-closing-title">'+esc(title)+'</p><p class="mag-closing-body">본 아티클은 정보 제공 목적이며, 정확한 진단과 치료 방법은 전문의와의 상담을 통해 결정하시기 바랍니다.</p></div>';
  return html;
}
function buildFull(P,cat,title,kw,desc,hero,bodyHtml){
  const ldA={"@context":"https://schema.org","@type":"MedicalWebPage",headline:title,description:desc,inLanguage:"ko",author:{"@type":"Organization",name:"팝성형외과"},publisher:{"@type":"Organization",name:"팝성형외과"}};
  const ldF={"@context":"https://schema.org","@type":"FAQPage",mainEntity:P.faq.map(f=>({"@type":"Question",name:f.q,acceptedAnswer:{"@type":"Answer",text:f.a}}))};
  return '<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
    +'<title>'+esc(title)+' | 팝성형외과</title><meta name="description" content="'+esc(desc)+'"><meta name="keywords" content="'+esc(kw)+'">'
    +'<meta property="og:type" content="article"><meta property="og:title" content="'+esc(title)+'"><meta property="og:description" content="'+esc(desc)+'"><meta property="og:image" content="'+hero+'"><meta property="og:locale" content="ko_KR">'
    +'<script type="application/ld+json">'+JSON.stringify(ldA)+'<\/script>'+(P.faq.length?'<script type="application/ld+json">'+JSON.stringify(ldF)+'<\/script>':'')
    +'<style>@import url(\'https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&family=Noto+Serif+KR:wght@500;700&display=swap\');'+CSS+'</style></head><body>'
    +'<article class="mag-wrap"><p class="mag-tag">'+esc(cat)+' / 팝성형외과</p><h1 class="mag-title">'+esc(title)+'</h1>'
    +'<figure><img class="mag-hero" src="'+hero+'" width="720" height="405" alt="'+esc(cat+' '+title+' 대표 이미지')+'"></figure>'
    +bodyHtml+'</article></body></html>';
}
function toast(m){let t=document.getElementById('__t');if(!t){t=document.createElement('div');t.id='__t';t.style.cssText='position:fixed;bottom:28px;left:50%;transform:translateX(-50%);background:#1a1a2e;color:#fff;padding:12px 22px;border-radius:24px;font-size:13px;z-index:9999;transition:opacity .3s';document.body.appendChild(t);}t.textContent=m;t.style.opacity='1';clearTimeout(t._h);t._h=setTimeout(()=>t.style.opacity='0',1800);}
async function copySrc(){if(!CURHTML)return;try{await navigator.clipboard.writeText(CURHTML);toast('HTML 소스 복사 완료 (전체 페이지)');}catch(e){const w=window.open('','_blank');w.document.write('<pre>'+esc(CURHTML)+'</pre>');}}
async function copyRich(){if(!CURBODY)return;const body=CURBODY;
  try{await navigator.clipboard.write([new ClipboardItem({'text/html':new Blob([body],{type:'text/html'}),'text/plain':new Blob([(CURPOST&&CURPOST.content)||'',],{type:'text/plain'})})]);toast('본문 복사 완료 / 메타 제외 (에디터 본문에 붙여넣기)');}
  catch(e){try{await navigator.clipboard.writeText(body);toast('본문 복사 완료');}catch(_){alert('복사 실패: 브라우저 권한 확인');}}}
async function genMag(btn){
  const cat=document.getElementById('genCat').value;
  const old=btn.textContent; btn.disabled=true; btn.textContent='생성 중... (최대 1~2분)';
  try{
    const r=await fetch('/api/mag/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({category:cat})});
    const d=await r.json();
    if(d.ok){ await boot(); toast('생성 완료 / '+d.created+'개'+((d.errors&&d.errors.length)?(' (일부 실패 '+d.errors.length+')'):'')); }
    else { alert('실패: '+(d.error||'')); }
  }catch(e){ alert('오류: '+e.message); }
  finally{ btn.disabled=false; btn.textContent=old; }
}
async function genDay(btn){
  const plan=[].concat(Array(5).fill('눈성형'),Array(5).fill('리프팅'),Array(5).fill('코성형'));
  if(!confirm('하루 15편(눈5/리프팅5/코5)을 생성할까요?\n몇 분 정도 걸려요. 이 탭을 닫지 마세요.')) return;
  const old=btn.textContent; btn.disabled=true;
  const gm=document.getElementById('genCat'); const gmBtn=document.querySelector('[onclick="genMag(this)"]');
  if(gmBtn) gmBtn.disabled=true; if(gm) gm.disabled=true;
  let ok=0, fail=0;
  for(let i=0;i<plan.length;i++){
    btn.textContent='생성 중 '+(i+1)+'/15 ('+plan[i]+')...';
    try{
      const r=await fetch('/api/mag/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({category:plan[i]})});
      const d=await r.json();
      if(d&&d.ok) ok++; else fail++;
    }catch(e){ fail++; }
    try{ await boot(); }catch(e){}
  }
  btn.disabled=false; if(gmBtn) gmBtn.disabled=false; if(gm) gm.disabled=false; btn.textContent=old;
  toast('하루 15편 완료 / 성공 '+ok+(fail?(' / 실패 '+fail):''));
}
boot();
</script>
</body>
</html>"""


# ════════════════════════════════════════════
# 매거진 전용 데이터 소스 (블로그와 분리)
#   - 매거진 글:   magazine/<날짜(YYYYMMDD)>/*.txt
#   - 매거진 카드: magazine_cards/<날짜>/<날짜>_<파일stem>/card_*.png
#   블로그(output/)와 폴더가 완전히 분리되어, 매거진 탭에는 블로그 글이 보이지 않습니다.
# ════════════════════════════════════════════
MAG_OUTPUT = BASE_DIR / "magazine"
MAG_CARDS = BASE_DIR / "magazine_cards"
MAG_IMAGES = BASE_DIR / "magazine_images"   # 글별 사람 히어로 사진: magazine_images/<날짜>/<파일stem>.(png|jpg|jpeg|webp)

def _mag_hero_file(date_str, stem):
    d = MAG_IMAGES / date_str
    if not d.exists():
        return ""
    for ext in ("png", "jpg", "jpeg", "webp"):
        p = d / f"{stem}.{ext}"
        if p.exists():
            return f"/magimg/{date_str}/{p.name}"
    return ""

def get_mag_dates():
    if not MAG_OUTPUT.exists():
        return []
    return sorted([d.name for d in MAG_OUTPUT.iterdir() if d.is_dir() and d.name.isdigit()], reverse=True)[:30]

def get_mag_posts(date_str):
    folder = MAG_OUTPUT / date_str
    if not folder.exists():
        return []
    published = load_published()
    posts = []
    for f in sorted(folder.glob("*.txt")):
        content = f.read_text(encoding="utf-8")
        post_id = f"mag_{date_str}_{f.name}"
        info = {
            "filename": f.name,
            "date": date_str,
            "content": content,
            "post_id": post_id,
            "hero": _mag_hero_file(date_str, f.stem),
        }
        for line in content.split("\n")[:12]:
            if line.startswith("카테고리:"): info["category"] = line.replace("카테고리:", "").strip()
            elif line.startswith("키워드:"): info["keyword"] = line.replace("키워드:", "").strip()
            elif line.startswith("제목:"): info["title"] = line.replace("제목:", "").strip()
        info["published"] = published.get(post_id, False)
        posts.append(info)
    return posts

@app.route('/magimg/<date>/<filename>')
def serve_mag_image(date, filename):
    from flask import send_from_directory
    return send_from_directory(str(MAG_IMAGES / date), filename)

@app.route('/api/mag/data')
def api_mag_data():
    dates = get_mag_dates()
    return jsonify({
        "dates": dates,
        "posts_by_date": {d: get_mag_posts(d) for d in dates},
    })

@app.route('/api/mag/set_image', methods=['POST'])
def api_mag_set_image():
    data = request.get_json() or {}
    date = (data.get("date") or "").strip()
    filename = (data.get("filename") or "").strip()
    url = (data.get("url") or "").strip()
    if not date or not filename or Path(filename).name != filename or not filename.endswith(".txt"):
        return jsonify({"ok": False, "error": "잘못된 요청"}), 400
    if url and not (url.startswith("http://") or url.startswith("https://")):
        return jsonify({"ok": False, "error": "URL은 http(s)로 시작해야 해요"}), 400
    f = MAG_OUTPUT / date / filename
    if not f.exists():
        return jsonify({"ok": False, "error": "글 파일을 찾을 수 없어요"}), 404
    lines = [l for l in f.read_text(encoding="utf-8").split("\n") if not l.startswith("이미지:")]
    if url:
        pos = 0
        for i, l in enumerate(lines[:12]):
            if l.startswith("카테고리:"): pos = i + 1
            if l.startswith("제목:"): pos = i + 1; break
        lines.insert(pos, "이미지: " + url)
    f.write_text("\n".join(lines), encoding="utf-8")
    return jsonify({"ok": True, "url": url})

@app.route('/api/mag/cards')
def api_mag_cards():
    filename = request.args.get('filename', '')
    date = request.args.get('date', '')
    if not filename or not date:
        return jsonify([])
    stem = Path(filename).stem
    folder_name = f"{date}_{stem}"
    card_dir = MAG_CARDS / date / folder_name
    if not card_dir.exists():
        card_dir = MAG_CARDS / date / stem
        folder_name = stem
    if not card_dir.exists():
        return jsonify([])
    cards = sorted(card_dir.glob("card_*.png"))
    return jsonify([f"/magcards/{date}/{folder_name}/{c.name}" for c in cards])

@app.route('/magcards/<date>/<folder_name>/<filename>')
def serve_mag_card(date, folder_name, filename):
    from flask import send_from_directory
    return send_from_directory(str(MAG_CARDS / date / folder_name), filename)


# ════════════════════════════════════════════
# 매거진 생성기 (스타일 가이드 핵심 규칙 = 코드 내장 / 파일 의존 없음)
#   대시보드에서 직접 Anthropic API 호출 -> magazine/<날짜>/*.txt 저장
#   .env 에 ANTHROPIC_API_KEY 필요
# ════════════════════════════════════════════
MAG_MODEL = "claude-sonnet-4-6"   # 더 강한 품질을 원하면 "claude-opus-4-8" 등으로 변경

# 스타일 가이드 핵심 규칙(코드 내장). 가이드가 바뀌면 이 문자열만 손보면 됩니다.
MAG_STYLE_RULES = (
    "당신은 한국 성형외과 '팝성형외과'의 의료 콘텐츠 작가입니다. 아래 스타일을 반드시 지킵니다.\n"
    "[말투] 해요체 중심(~에요/예요/죠/수 있어요). 사실/정의/권고 문장만 합니다체 일부 혼용. 따뜻하고 차분한 상담 어조. 이모지 금지.\n"
    "[도입] 공감 질문 -> 통념 반전('~가 아닐 수도 있어요') -> 글 목적 안내, 3단으로.\n"
    "[본문] 질문형 소제목 4개(예: '~나요?' '~까요?'). 각 섹션 첫 문장은 핵심을 한 문장으로 명료히 정의. 의학 용어는 쓴 즉시 쉬운 말로 풀이.\n"
    "[금지] 단정/보장/최상급(최고/유일/1위/100%/반드시), 경쟁 병원 비방, 가격/이벤트 등 환자 유인 표현. 효과는 '~할 수 있어요/경우가 많아요/개인마다 달라요'로 서술.\n"
    "[리프팅 범위] 울쎄라/써마지 등 장비 브랜드 시술은 자사 시술로 소개/추천 금지. 비교 목적 언급만 가능하며 우열 단정 금지(중립적 차이 설명). 보톡스/필러 등 주사 시술류는 다루지 않음.\n"
    "[FAQ] 자연어 질문 3개와 해요체 답변(각 2~3문장).\n"
)

# 카테고리별 주제 범위(코드 내장)
MAG_CAT_SCOPE = {
    "눈성형": "쌍꺼풀, 눈매교정, 트임, 눈재수술, 지방재배치 등 눈 성형",
    "리프팅": "안면거상(수술)과 실리프팅 중심 (주사 시술류/장비 브랜드 시술 제외, 비교만 가능)",
    "코성형": "융비술, 콧대/코끝 성형, 코재수술, 휜코/매부리코 교정 등 코 성형",
}


def _mag_recent_keywords(cat):
    """같은 카테고리에서 이미 쓴 키워드(중복 주제 회피용)"""
    kws = []
    if not MAG_OUTPUT.exists():
        return kws
    for d in MAG_OUTPUT.iterdir():
        if not d.is_dir():
            continue
        for f in d.glob("*.txt"):
            try:
                head = f.read_text(encoding="utf-8").split("\n")[:8]
            except Exception:
                continue
            c = k = ""
            for line in head:
                if line.startswith("카테고리:"): c = line.replace("카테고리:", "").strip()
                elif line.startswith("키워드:"): k = line.replace("키워드:", "").strip()
            if c == cat and k:
                kws.append(k)
    return kws


def _mag_clean(text, cat, today):
    """코드펜스 제거 + 헤더(카테고리/생성일) 보정"""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    t = t.strip()
    lines = t.split("\n")
    head = "\n".join(lines[:8])
    if "카테고리:" not in head:
        t = "카테고리: " + cat + "\n" + t
        lines = t.split("\n")
    else:
        # 카테고리 값 강제 정렬
        for i, ln in enumerate(lines[:8]):
            if ln.startswith("카테고리:"):
                lines[i] = "카테고리: " + cat
                break
        t = "\n".join(lines)
    if "생성일:" not in "\n".join(t.split("\n")[:8]):
        # 제목 줄 뒤에 생성일 삽입(없으면 맨 위 근처에)
        parts = t.split("\n")
        insert_at = 1
        for i, ln in enumerate(parts[:8]):
            if ln.startswith("제목:"):
                insert_at = i + 1
                break
        parts.insert(insert_at, "생성일: " + today)
        t = "\n".join(parts)
    return t.strip() + "\n"


def _mag_call(category, recent):
    """Anthropic API 직접 호출 -> .txt 본문(플레인 텍스트) 반환"""
    import os
    import urllib.request as urlreq
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError(".env에 ANTHROPIC_API_KEY가 없어요")
    today_kr = datetime.now().strftime("%Y-%m-%d")
    scope = MAG_CAT_SCOPE.get(category, category)
    avoid = ("이미 다룬 주제는 피하세요: " + ", ".join(recent[:20]) + "\n") if recent else ""
    user = (
        "카테고리: " + category + "\n"
        "이 카테고리 범위: " + scope + "\n"
        + avoid +
        "위 범위에서 적절한 주제 1개를 직접 정해 글을 쓰세요.\n\n"
        "반드시 아래 '플레인 텍스트' 형식으로만 출력하세요. 마크다운 코드펜스(```)/해설/머리말 금지.\n"
        "헤더 항목은 한 줄씩 그대로, 소제목은 반드시 '## '로 시작, FAQ는 'Q1.'/'A1.' 형식을 지키세요.\n"
        "--- 형식 시작 ---\n"
        "카테고리: " + category + "\n"
        "키워드: <핵심 키워드 1개>\n"
        "제목: <키워드를 앞쪽에 둔 25~40자 제목>\n"
        "슬러그: <영문 소문자-하이픈 URL, 3~6단어>\n"
        "요약: <리스트 노출용 1~2문장, 60~120자>\n"
        "SEO키워드: <쉼표로 구분한 6~8개>\n"
        "SEO설명: <메타 설명 70~90자>\n"
        "노출여부: 공개\n"
        "게시일시: \n"
        "생성일: " + today_kr + "\n"
        "==============================\n"
        "<도입 2~3문장: 공감 질문 -> 통념 반전 -> 목적 안내>\n\n"
        "## <질문형 소제목 1>\n<2~3문장, 첫 문장은 핵심 정의>\n[핵심] <항목1> | <항목2> | <항목3>\n\n"
        "## <질문형 소제목 2>\n<2~3문장>\n[핵심] <항목1> | <항목2> | <항목3>\n\n"
        "## <질문형 소제목 3>\n<2~3문장>\n[핵심] <항목1> | <항목2> | <항목3>\n\n"
        "## <질문형 소제목 4>\n<2~3문장>\n[핵심] <항목1> | <항목2> | <항목3>\n\n"
        "[인포그래픽] <인포그래픽 제목> | <핵심 항목1> | <핵심 항목2> | <핵심 항목3>\n"
        "[비교] <왼쪽 제목> | <항목1>;<항목2>;<항목3> | <오른쪽 제목> | <항목1>;<항목2>;<항목3>\n"
        "[데이터] <라벨1> | <값1> | <라벨2> | <값2> | <라벨3> | <값3>\n\n"
        "Q1. <질문>\nA1. <답변(해요체)>\n"
        "Q2. <질문>\nA2. <답변>\n"
        "Q3. <질문>\nA3. <답변>\n"
        "--- 형식 끝 ---\n"
        "주의: '## ' 소제목 4개(각 뒤에 '[핵심]' 한 줄), 'Q1./A1.' FAQ 3개, '[인포그래픽]'/'[비교]'/'[데이터]' 각 1줄을 반드시 포함하세요. "
        "[비교]의 항목은 세미콜론(;)으로, 칸은 막대(|)로 구분합니다. [데이터]의 값은 '1~2년','2주' 같은 짧은 수치로 적으세요.\n"
    )
    body = json.dumps({
        "model": MAG_MODEL,
        "max_tokens": 4000,
        "system": MAG_STYLE_RULES,
        "messages": [{"role": "user", "content": user}],
    }, ensure_ascii=False).encode("utf-8")
    req = urlreq.Request(
        "https://api.anthropic.com/v1/messages",
        data=body, method="POST",
        headers={
            "Content-Type": "application/json",
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        },
    )
    with urlreq.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


# ════════════════════════════════════════════
# Higgsfield 로컬 이미지 자동 생성 (선택, 비차단)
#   .env 에 아래가 모두 설정돼야 동작합니다. 하나라도 없으면 이미지 단계를 조용히 건너뛰고
#   대시보드는 기존 SVG 히어로로 폴백해요(글 생성은 절대 안 깨짐).
#     HIGGSFIELD_API_KEY      = <발급키>
#     HIGGSFIELD_CREATE_URL   = <이미지 생성 POST 엔드포인트>      <- 본인 API 문서대로
#     HIGGSFIELD_RESULT_URL   = <결과 조회 GET 엔드포인트, {id} 포함>  (동기 응답이면 생략 가능)
#   선택: HIGGSFIELD_API_SECRET, HIGGSFIELD_IMAGE_MODEL(기본 recraft-v4-1),
#         HIGGSFIELD_AUTH_HEADER(기본 hf-api-key)
#   ※ 엔드포인트/응답 형식은 환경마다 달라서 추측으로 박지 않았어요. 본인 API의 curl을 주시면 정확히 맞춰드립니다.
# ════════════════════════════════════════════
HF_STYLE = ("bright natural editorial photograph, Korean person, realistic natural skin texture and pores, "
            "soft daylight, lived-in natural background softly blurred (home, cafe, clinic lobby), "
            "photorealistic, candid, not glossy, not over-retouched, not AI-looking, no text")
HF_CONCERN = {
    "눈성형": ["heavy drooping upper eyelids and sleepy tired-looking eyes",
              "asymmetric uneven double eyelids", "small mono-lid eyes looking tired"],
    "리프팅": ["sagging cheeks and loose jowls along the jawline",
              "deepening nasolabial folds and lower-face sagging"],
    "코성형": ["a slightly crooked deviated nasal bridge, three-quarter side view",
              "an upturned snub nose (deulchang-ko), three-quarter side view",
              "a humped dorsal nasal bridge, side profile"],
}

def _mag_image_prompt(category, keyword):
    import random
    kw = keyword or ""
    cue = random.choice(HF_CONCERN.get(category, [""]))
    if "들창" in kw: cue = "an upturned snub nose (deulchang-ko), three-quarter side view"
    elif "비뚤" in kw or "휜" in kw or "휘" in kw: cue = "a slightly crooked deviated nasal bridge, three-quarter side view"
    elif "매부리" in kw: cue = "a humped dorsal nasal bridge, side profile"
    elif "안검" in kw or "처진" in kw or "졸려" in kw or "눈매" in kw: cue = "heavy drooping upper eyelids and sleepy tired-looking eyes"
    elif "거상" in kw or "처짐" in kw or "탄력" in kw: cue = "sagging cheeks and loose jowls along the jawline"
    gender, poss = random.choice([("Korean woman", "her"), ("Korean man", "his")])
    age = random.choice(["in their early 20s", "in their late 20s", "in their 30s", "in their 40s"])
    expr = random.choice(["calm neutral expression", "slightly concerned expression", "thoughtful expression"])
    return ("Natural candid editorial photograph of a " + gender + " " + age + " indoors with soft daylight, "
            "clearly showing " + cue + ", " + expr + " (not forced smiling), " + HF_STYLE)

def _hf_extract_url(d):
    """응답 JSON에서 이미지 URL을 best-effort로 추출"""
    if not isinstance(d, dict):
        return ""
    for k in ("result_url", "image_url", "url", "output_url"):
        v = d.get(k)
        if isinstance(v, str) and v.startswith("http"):
            return v
    for k in ("results", "output", "images", "data"):
        v = d.get(k)
        if isinstance(v, list) and v:
            it = v[0]
            if isinstance(it, str) and it.startswith("http"):
                return it
            if isinstance(it, dict):
                for kk in ("url", "result_url", "image_url"):
                    if isinstance(it.get(kk), str) and it[kk].startswith("http"):
                        return it[kk]
    return ""

def hf_generate_image(prompt, aspect_ratio="16:9", model=""):
    """Higgsfield 로컬 이미지 생성. 미설정/실패 시 빈 문자열 반환(비차단)."""
    import os, time
    import urllib.request as urlreq
    key = os.environ.get("HIGGSFIELD_API_KEY", "")
    create = os.environ.get("HIGGSFIELD_CREATE_URL", "")
    if not key or not create:
        return ""   # 미설정 -> 이미지 단계 건너뜀
    auth_header = os.environ.get("HIGGSFIELD_AUTH_HEADER", "hf-api-key")
    headers = {"Content-Type": "application/json", auth_header: key}
    secret = os.environ.get("HIGGSFIELD_API_SECRET", "")
    if secret:
        headers["hf-secret"] = secret
    payload = {
        "model": model or os.environ.get("HIGGSFIELD_IMAGE_MODEL", "recraft-v4-1"),
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
    }
    try:
        req = urlreq.Request(create, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urlreq.urlopen(req, timeout=60) as r:
            d = json.loads(r.read().decode("utf-8"))
        url = _hf_extract_url(d)
        if url:
            return url
        job = d.get("id") or d.get("job_id")
        result_tmpl = os.environ.get("HIGGSFIELD_RESULT_URL", "")
        if job and result_tmpl:
            for _ in range(30):
                time.sleep(4)
                rq = urlreq.Request(result_tmpl.replace("{id}", str(job)), headers=headers)
                with urlreq.urlopen(rq, timeout=30) as r2:
                    jd = json.loads(r2.read().decode("utf-8"))
                url = _hf_extract_url(jd)
                if url:
                    return url
    except Exception:
        return ""
    return ""

def _inject_header(text, key, val):
    lines = text.split("\n")
    pos = 0
    for i, l in enumerate(lines[:10]):
        if l.startswith("카테고리:"):
            pos = i + 1
        if l.startswith("제목:"):
            pos = i + 1
            break
    lines.insert(pos, key + ": " + val)
    return "\n".join(lines)

def _extract_keyword(text):
    for l in text.split("\n")[:12]:
        if l.startswith("키워드:"):
            return l.replace("키워드:", "").strip()
    return ""


#   매거진 생성은 magazine_run.py 로 위임합니다 (FAQ 스키마/내부 링크/말투/감수자 최적화 포함).
#   magazine_run.py 위치: 기본은 대시보드와 같은 폴더. 다르면 .env 의 MAGAZINE_RUN_PATH 로 지정.
MAGAZINE_RUN_PATH = Path(os.environ.get("MAGAZINE_RUN_PATH", str(BASE_DIR / "magazine_run.py")))


@app.route('/api/mag/generate', methods=['POST'])
def api_mag_generate():
    import os as _os
    import sys as _sys
    import subprocess as _sp

    data = request.get_json() or {}
    cat = (data.get("category") or "").strip()
    try:
        count = int(data.get("count") or 1)
    except (TypeError, ValueError):
        count = 1
    count = max(1, min(count, 10))

    if not MAGAZINE_RUN_PATH.exists():
        return jsonify({"ok": False, "error": "magazine_run.py 를 찾을 수 없어요: " + str(MAGAZINE_RUN_PATH)}), 500

    cat_en = {"눈성형": "eye", "리프팅": "lifting", "코성형": "nose"}
    # 특정 카테고리면 그 카테고리로 count 개, 아니면 눈/리프팅/코 각 1개씩
    if cat in cat_en:
        jobs = [(cat_en[cat], count)]
    else:
        jobs = [("eye", 1), ("lifting", 1), ("nose", 1)]

    # magazine_run 이 대시보드의 magazine/ 폴더에 .txt 로 저장하도록 환경변수 지정
    env = dict(_os.environ)
    env["MAGAZINE_OUTPUT_DIR"] = str(MAG_OUTPUT)
    env["MAGAZINE_OUTPUT_EXT"] = "txt"

    created, errors = 0, []
    for category_en, n in jobs:
        cmd = [_sys.executable, str(MAGAZINE_RUN_PATH),
               "--category", category_en, "--count", str(n), "--additive"]
        try:
            r = _sp.run(cmd, cwd=str(MAGAZINE_RUN_PATH.parent),
                        capture_output=True, text=True, timeout=900, env=env)
            if r.returncode != 0:
                errors.append(f"{category_en}: {(r.stderr or r.stdout or '').strip()[-300:]}")
            else:
                created += n
        except Exception as e:
            errors.append(f"{category_en}: {e}")

    if created == 0:
        return jsonify({"ok": False, "error": "; ".join(errors) or "생성 실패"}), 500
    return jsonify({"ok": True, "created": created, "errors": errors})




@app.route("/magazine")
def magazine_page():
    return render_template_string(MAG_HTML)


# ============================================================
#   카드뉴스(인스타 캐러셀) 탭 - node generate.mjs + render.mjs 를 버튼으로
#   덱 개수만큼 생성하고, 각 덱(8장)을 decks/<배치>/deck-NN/ 에 보관/미리보기
# ============================================================
import os as _cn_os
from pathlib import Path as _CNPath

# 카드뉴스 프로젝트 폴더 (generate.mjs / render.mjs / shared / assets 가 있는 곳)
CARDNEWS_DIR = _cn_os.environ.get(
    "CARDNEWS_DIR",
    "C:/Users/USER/Desktop/instagram-card-news/face-note-01",
)

CN_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>POP 카드뉴스</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
body{background:#f5f5f7;color:#1a1a2e;font-family:'Noto Sans KR',sans-serif;min-height:100vh}
.topnav{background:#1a1a2e;display:flex;padding:0 24px}
.topnav a{padding:13px 22px;font-size:13px;color:#a0a0c0;text-decoration:none;border-bottom:3px solid transparent;display:block}
.topnav a:hover{color:#a78bfa}
.topnav a.on{color:#a78bfa;border-bottom-color:#a78bfa}
.header{background:#fff;border-bottom:1px solid rgba(0,0,0,0.08);padding:14px 24px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;position:sticky;top:0;z-index:100}
.logo{font-size:17px;font-weight:700;color:#7c6af7}.logo span{color:#8888a8;font-weight:300}
.controls{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.controls input[type=text]{width:240px;background:#f9f9fb;border:1px solid rgba(0,0,0,0.1);padding:8px 12px;border-radius:8px;font-family:inherit;font-size:13px}
.controls input[type=number]{width:64px;background:#f9f9fb;border:1px solid rgba(0,0,0,0.1);padding:8px 10px;border-radius:8px;font-family:inherit;font-size:13px}
.controls label{font-size:13px;color:#555;display:flex;align-items:center;gap:5px}
.btn-gen{background:linear-gradient(135deg,#6355e8,#5b4fe8);color:#fff;border:none;padding:9px 18px;border-radius:8px;font-size:13px;font-family:inherit;font-weight:500;cursor:pointer}
.btn-gen:disabled{opacity:.5;cursor:not-allowed}
.wrap{padding:24px;max-width:1200px;margin:0 auto}
.batch{margin-bottom:30px}
.batch h3{font-size:14px;color:#555;margin-bottom:12px;font-weight:600}
.deck{background:#fff;border:1px solid rgba(0,0,0,0.08);border-radius:12px;padding:14px;margin-bottom:14px}
.deck .dlabel{font-size:12px;color:#8888a8;margin-bottom:10px;font-weight:600}
.cards{display:grid;grid-template-columns:repeat(8,1fr);gap:8px}
@media(max-width:1000px){.cards{grid-template-columns:repeat(4,1fr)}}
.cards img{width:100%;aspect-ratio:1080/1350;object-fit:cover;border-radius:8px;border:1px solid rgba(0,0,0,0.08);cursor:pointer;background:#e8e2d8}
.hint{font-size:12px;color:#8888a8;margin-bottom:16px;line-height:1.6;background:#fff;border:1px solid rgba(0,0,0,0.06);border-radius:10px;padding:12px 14px}
.empty{text-align:center;color:#8888a8;padding:60px 0;font-size:14px}
.overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:999;align-items:center;justify-content:center;flex-direction:column;gap:14px}
.overlay.show{display:flex}
.spinner{width:36px;height:36px;border:3px solid rgba(99,85,232,0.3);border-top-color:#6355e8;border-radius:50%;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.overlaytext{color:#fff;font-size:14px}
</style>
</head>
<body>
<div class="topnav">
  <a href="/">📝 블로그</a>
  <a href="/youtube">🎬 유튜브 스크립트</a>
  <a href="/magazine">📰 매거진</a>
  <a href="/cardnews" class="on">🖼 카드뉴스</a>
  <a href="/threads">🧵 스레드</a>
</div>
<div class="header">
  <div class="logo">POP <span>카드뉴스</span></div>
  <div class="controls">
    <input type="text" id="topic" placeholder="주제 (비우면 자동)">
    <label>덱 개수 <input type="number" id="count" value="1" min="1" max="20"></label>
    <label><input type="checkbox" id="photos"> 사진 포함</label>
    <button class="btn-gen" onclick="generate()">▶ 생성</button>
  </div>
</div>
<div class="wrap">
  <div class="hint">주제를 비우면 자동 주제로 만들어요. 덱마다 레이아웃이 달라져요(타이포 / 인포그래픽 / 단색). ‘사진 포함'은 <b>assets/images/</b> 에 cover.png / card03.png / cta.png 가 있을 때만 사진 카드가 들어가요(사진은 이 채팅에서 받아 그 폴더에 넣어두세요). 썸네일을 클릭하면 원본 PNG가 열려요.</div>
  <div id="results"><div class="empty">불러오는 중...</div></div>
</div>
<div class="overlay" id="overlay"><div class="spinner"></div><div class="overlaytext" id="ovtext">생성 중...</div></div>
<script>
function openImg(s){window.open(s,'_blank');}
async function loadDecks(){
  const el=document.getElementById('results');
  try{
    const r=await fetch('/api/cn/decks');const b=await r.json();
    if(!b.length){el.innerHTML='<div class="empty">아직 생성된 카드뉴스가 없어요. 위에서 ▶ 생성을 눌러보세요.</div>';return;}
    el.innerHTML=b.map(batch=>`
      <div class="batch"><h3>📅 ${batch.batch} / ${batch.decks.length}덱</h3>
      ${batch.decks.map(d=>`
        <div class="deck"><div class="dlabel">${d.deck} / ${d.images.length}장</div>
        <div class="cards">${d.images.map(img=>{
          const src='/cnimg/'+batch.batch+'/'+d.deck+'/'+img;
          return '<img src="'+src+'" onclick="openImg(this.src)" title="'+img+'">';
        }).join('')}</div></div>`).join('')}
      </div>`).join('');
  }catch(e){el.innerHTML='<div class="empty">목록을 불러오지 못했어요: '+e.message+'</div>';}
}
async function generate(){
  const topic=document.getElementById('topic').value.trim();
  const count=parseInt(document.getElementById('count').value||'1',10);
  const photos=document.getElementById('photos').checked;
  const btn=document.querySelector('.btn-gen');const ov=document.getElementById('overlay');
  btn.disabled=true;ov.classList.add('show');
  document.getElementById('ovtext').textContent=count+'개 덱 생성 중... (글/렌더 때문에 몇 분 걸려요. 탭을 닫지 마세요)';
  try{
    const r=await fetch('/api/cn/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({topic:topic,count:count,photos:photos})});
    const d=await r.json();
    if(d.success){await loadDecks(); if(d.photo_note) alert(d.photo_note);}
    else alert('실패: '+d.error);
  }catch(e){alert('오류: '+e.message);}
  finally{btn.disabled=false;ov.classList.remove('show');}
}
loadDecks();
</script>
</body>
</html>"""


@app.route("/cardnews")
def cardnews_page():
    return render_template_string(CN_HTML)


@app.route("/api/cn/decks")
def api_cn_decks():
    base = _CNPath(CARDNEWS_DIR) / "decks"
    batches = []
    if base.exists():
        for bdir in sorted(base.iterdir(), reverse=True):
            if not bdir.is_dir():
                continue
            decks = []
            for ddir in sorted(bdir.iterdir()):
                if not ddir.is_dir():
                    continue
                imgs = [p.name for p in sorted(ddir.glob("*.png"))]
                if imgs:
                    decks.append({"deck": ddir.name, "images": imgs})
            if decks:
                batches.append({"batch": bdir.name, "decks": decks})
    return jsonify(batches)


@app.route("/cnimg/<batch>/<deck>/<filename>")
def serve_cn_image(batch, deck, filename):
    from flask import send_from_directory
    if not filename.lower().endswith(".png"):
        return ("", 404)
    folder = _CNPath(CARDNEWS_DIR) / "decks" / batch / deck
    return send_from_directory(str(folder), filename)


def _cn_make_photos(cn_dir):
    """photo-jobs.json 을 읽어 Higgsfield REST 로 사진 생성 -> assets/images/<file> 저장.
       반환: dict(made, total, configured). HF 미설정이면 configured=False (사진 단계 건너뜀)."""
    import urllib.request as _ur
    jobs_file = cn_dir / "photo-jobs.json"
    if not jobs_file.exists():
        return {"made": 0, "total": 0, "configured": True}
    try:
        spec = json.loads(jobs_file.read_text(encoding="utf-8"))
    except Exception:
        return {"made": 0, "total": 0, "configured": True}
    jobs = spec.get("jobs", []) or []
    if not jobs:
        return {"made": 0, "total": 0, "configured": True}
    if not (_cn_os.environ.get("HIGGSFIELD_API_KEY") and _cn_os.environ.get("HIGGSFIELD_CREATE_URL")):
        return {"made": 0, "total": len(jobs), "configured": False}
    img_dir = cn_dir / "assets" / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    model = _cn_os.environ.get("HIGGSFIELD_CARDNEWS_MODEL", "nano-banana-pro")
    made = 0
    for job in jobs:
        fname = (job.get("file") or "").strip()
        prompt = (job.get("prompt") or "").strip()
        if not fname or not prompt or _CNPath(fname).name != fname:
            continue
        url = hf_generate_image(prompt, aspect_ratio="4:5", model=model)
        if not url:
            continue
        try:
            with _ur.urlopen(url, timeout=180) as r:
                (img_dir / fname).write_bytes(r.read())
            made += 1
        except Exception:
            continue
    return {"made": made, "total": len(jobs), "configured": True}


@app.route("/api/cn/generate", methods=["POST"])
def api_cn_generate():
    import subprocess as _sp
    import shutil as _sh
    import time as _t
    try:
        data = request.json or {}
        topic = (data.get("topic") or "").strip()
        try:
            count = int(data.get("count") or 1)
        except (TypeError, ValueError):
            count = 1
        count = max(1, min(count, 20))
        photos = bool(data.get("photos"))

        cn_dir = _CNPath(CARDNEWS_DIR)
        if not cn_dir.exists():
            return jsonify({"success": False, "error": "카드뉴스 폴더가 없어요: " + CARDNEWS_DIR})
        if not (cn_dir / "generate.mjs").exists() or not (cn_dir / "render.mjs").exists():
            return jsonify({"success": False, "error": "generate.mjs / render.mjs 를 찾을 수 없어요: " + CARDNEWS_DIR})

        base_env = dict(_cn_os.environ)
        # CARD_PHOTOS 는 명시적으로 1/0 지정 (.env 의 기본값에 덮이지 않도록)
        base_env["CARD_PHOTOS"] = "1" if photos else "0"

        batch = _t.strftime("%Y%m%d-%H%M%S")
        out_dir = cn_dir / "output"
        decks = []
        photo_note = ""

        for i in range(1, count + 1):
            env = dict(base_env)
            env["CARD_SEED"] = str(i - 1)  # 덱마다 레이아웃 다르게

            gen_cmd = ["node", "generate.mjs"] + ([topic] if topic else [])
            r1 = _sp.run(gen_cmd, cwd=str(cn_dir), capture_output=True, text=True, timeout=300, env=env)
            if r1.returncode != 0:
                return jsonify({"success": False, "error": "덱 %d 글 생성 실패: %s" % (i, (r1.stderr or r1.stdout or "").strip())})

            # 사진 모드면 photo-jobs.json 의 프롬프트로 Higgsfield 공식 SDK 사진 생성 -> assets/images/
            if photos and (cn_dir / "photos.mjs").exists():
                rp = _sp.run(["node", "photos.mjs"], cwd=str(cn_dir), capture_output=True, text=True, timeout=600, env=env)
                line = ""
                for ln in (rp.stdout or "").splitlines():
                    if ln.startswith("PHOTOS:"):
                        line = ln.replace("PHOTOS:", "").strip()
                if line:
                    photo_note = "사진: " + line

            r2 = _sp.run(["node", "render.mjs"], cwd=str(cn_dir), capture_output=True, text=True, timeout=300, env=env)
            if r2.returncode != 0:
                return jsonify({"success": False, "error": "덱 %d 렌더 실패: %s" % (i, (r2.stderr or r2.stdout or "").strip())})

            deck_dir = cn_dir / "decks" / batch / ("deck-%02d" % i)
            deck_dir.mkdir(parents=True, exist_ok=True)
            imgs = []
            for png in sorted(out_dir.glob("*.png")):
                _sh.copy2(png, deck_dir / png.name)
                imgs.append(png.name)
            decks.append({"deck": "deck-%02d" % i, "images": imgs})

        return jsonify({"success": True, "batch": batch, "decks": decks, "photo_note": photo_note})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})



# ════════════════════════════════════════════
# 스레드 대시보드
# ════════════════════════════════════════════

THREADS_DIR = BASE_DIR / "threads_output"
THREADS_PUBLISHED_FILE = BASE_DIR / "threads_published.json"

THREAD_PERSONA = {
    "role": "24년차 쌍꺼풀 수술 전문 성형외과 전문의",
    "tone": "남성 의사, ~요체, 짧고 사람 말투, 딱딱하지 않게",
    "interests": "마라톤, 책, 마케팅 공부, 반려견"
}

THREAD_HTML = r"""
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>POP 스레드 대시보드</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI','Noto Sans KR',sans-serif;background:#f0f2f5;color:#333}
.nav{background:#1a1a2e;border-bottom:2px solid rgba(167,139,250,.2);padding:0 24px;display:flex;position:sticky;top:0;z-index:999}
.nav a{padding:13px 22px;font-size:13px;font-weight:500;color:#a0a0c0;text-decoration:none;border-bottom:3px solid transparent;margin-bottom:-2px}
.nav a.on{color:#a78bfa;border-bottom-color:#a78bfa}
.header{background:linear-gradient(135deg,#1a1a2e,#16213e);color:#fff;padding:18px 30px;display:flex;justify-content:space-between;align-items:center}
.header h1{font-size:19px;font-weight:600}.header span{font-size:12px;color:#aaa}
.wrap{max-width:1280px;margin:0 auto;padding:22px 24px 60px}
.panel{background:#fff;border-radius:14px;box-shadow:0 2px 8px rgba(0,0,0,.06);padding:18px;margin-bottom:18px}
.controls{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.btn{padding:9px 16px;border:1px solid #ddd;background:#fff;border-radius:9px;font-size:13px;font-weight:700;cursor:pointer}.btn.p{background:#6355e8;color:#fff;border-color:#6355e8}.btn:disabled{opacity:.5;cursor:not-allowed}
.date-tabs{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}.date-tab{padding:6px 14px;border:1px solid #ddd;background:#fff;border-radius:20px;font-size:12px;cursor:pointer}.date-tab.on{background:#1a1a2e;color:#fff;border-color:#1a1a2e}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.stat{background:#fafafa;border:1px solid #eee;border-radius:12px;padding:14px}.stat .l{font-size:12px;color:#888;margin-bottom:5px}.stat .v{font-size:24px;font-weight:800;color:#1a1a2e}
.list{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}.card{border:1px solid #eee;border-radius:14px;padding:16px;background:#fff;position:relative}.card.done{opacity:.55}.meta{display:flex;gap:6px;align-items:center;margin-bottom:10px}.badge{font-size:11px;padding:3px 9px;border-radius:20px;font-weight:700}.b-참여형{background:#f3efff;color:#7c5fe6}.b-정보형{background:#e8f0fe;color:#4f8ef7}.b-일상형{background:#e8faf3;color:#22a06b}.num{margin-left:auto;font-size:11px;color:#aaa}.text{font-size:14px;line-height:1.75;white-space:pre-wrap;color:#222;margin-bottom:12px}.actions{display:flex;gap:8px}.small{padding:6px 11px;border-radius:8px;border:1px solid #ddd;background:#fff;font-size:12px;cursor:pointer}.small.pub{border-color:#2ecc71;color:#2ecc71}.small.copy{border-color:#6355e8;color:#6355e8}.empty{text-align:center;color:#aaa;padding:40px}.guide{font-size:12px;color:#777;line-height:1.7}.mix{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}.mix span{background:#f7f7fb;border:1px solid #ececf4;border-radius:18px;padding:5px 10px;font-size:12px;color:#666}
@media(max-width:900px){.list,.stats{grid-template-columns:1fr}.nav{overflow-x:auto}}
</style>
</head>
<body>
<div class="nav">
  <a href="/">📝 블로그</a>
  <a href="/youtube">🎬 유튜브 스크립트</a>
  <a href="/magazine">📰 매거진</a>
  <a href="/cardnews">🖼 카드뉴스</a>
  <a href="/threads" class="on">🧵 스레드</a>
</div>
<div class="header"><h1>🧵 POP 스레드 대시보드</h1><span>24년차 전문의 톤 / 하루 10개 짧은 글</span></div>
<div class="wrap">
  <div class="panel">
    <div class="controls">
      <button class="btn p" id="genBtn" onclick="generateThreads()">오늘 10개 생성/업데이트</button>
      <button class="btn" onclick="loadData()">새로고침</button>
      <span class="guide">비율: 참여형 3 / 정보형 5 / 일상형 2 / 길이: 짧게 / 말투: ~요</span>
    </div>
    <div class="mix"><span>첫 문장 훅</span><span>댓글 유도</span><span>의료광고 안전표현</span><span>마라톤/책/마케팅/강아지 일상 반영</span></div>
    <div class="date-tabs" id="dateTabs"></div>
  </div>
  <div class="stats" id="stats"></div>
  <div class="panel"><div class="list" id="list"><div class="empty">불러오는 중...</div></div></div>
</div>
<script>
let DATA={dates:[], posts_by_date:{}}, CUR=null;
async function loadData(){const r=await fetch('/api/threads/data');DATA=await r.json();if(!CUR&&DATA.dates.length)CUR=DATA.dates[0];render();}
function render(){renderDates();renderStats();renderList();}
function renderDates(){const el=document.getElementById('dateTabs');el.innerHTML=(DATA.dates||[]).map(d=>`<button class="date-tab ${d===CUR?'on':''}" onclick="CUR='${d}';render()">${d.slice(4,6)}/${d.slice(6,8)}</button>`).join('');}
function curPosts(){return (DATA.posts_by_date[CUR]||[])}
function renderStats(){const p=curPosts();const c=t=>p.filter(x=>x.type===t).length;const done=p.filter(x=>x.published).length;document.getElementById('stats').innerHTML=`<div class="stat"><div class="l">전체 / 발행완료</div><div class="v">${p.length} / ${done}</div></div><div class="stat"><div class="l">참여형</div><div class="v">${c('참여형')}</div></div><div class="stat"><div class="l">정보형</div><div class="v">${c('정보형')}</div></div><div class="stat"><div class="l">일상형</div><div class="v">${c('일상형')}</div></div>`;}
function esc(s){return String(s||'').replace(/[&<>]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[m]));}
function renderList(){const p=curPosts();const el=document.getElementById('list');if(!p.length){el.innerHTML='<div class="empty">아직 생성된 스레드가 없어요. 오늘 10개 생성을 눌러주세요.</div>';return;}el.innerHTML=p.map((x,i)=>`<div class="card ${x.published?'done':''}"><div class="meta"><span class="badge b-${x.type}">${x.type}</span><span class="num">#${i+1} / ${x.length}자</span></div><div class="text" id="t-${x.id}">${esc(x.text)}</div><div class="actions"><button class="small copy" onclick="copyText('${x.id}')">복사</button><button class="small pub" onclick="togglePub('${x.id}')">${x.published?'✅ 발행완료':'⬜ 미발행'}</button></div></div>`).join('');}
async function generateThreads(){const btn=document.getElementById('genBtn');btn.disabled=true;btn.textContent='생성 중...';try{const r=await fetch('/api/threads/generate',{method:'POST'});const d=await r.json();if(!d.success)alert(d.error||'생성 실패');CUR=d.date||CUR;await loadData();CUR=d.date||CUR;render();}catch(e){alert('오류: '+e.message)}finally{btn.disabled=false;btn.textContent='오늘 10개 생성/업데이트';}}
async function togglePub(id){const r=await fetch('/api/threads/toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});const d=await r.json();for(const date in DATA.posts_by_date){DATA.posts_by_date[date].forEach(x=>{if(x.id===id)x.published=d.published;});}render();}
function copyText(id){const el=document.getElementById('t-'+id);navigator.clipboard.writeText(el.innerText).then(()=>alert('복사 완료!'));}
loadData();
</script>
</body>
</html>
"""

def _threads_today():
    return datetime.now().strftime('%Y%m%d')

def _load_threads_published():
    if THREADS_PUBLISHED_FILE.exists():
        try:
            return json.loads(THREADS_PUBLISHED_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def _save_threads_published(data):
    THREADS_PUBLISHED_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def _thread_file(date_str):
    THREADS_DIR.mkdir(parents=True, exist_ok=True)
    return THREADS_DIR / f"{date_str}.json"

def _safe_short(text, limit=170):
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[:limit-1].rstrip() + "..."

def _default_threads():
    # 짧은 글: 참여형 3개, 정보형 5개, 일상형 2개
    items = [
        ("참여형", "쌍꺼풀 상담 때 제일 많이 틀리는 질문이 있어요. ‘라인 몇 mm가 예뻐요?'보다 먼저 봐야 하는 건 눈 뜨는 힘이에요. 여러분은 라인 높이랑 눈 뜨는 힘 중 뭐가 더 중요하다고 생각하세요?"),
        ("참여형", "사진 찍을 때 눈이 달라 보이면 수술이 문제일까요? 꼭 그렇진 않아요. 렌즈, 각도, 눈썹 힘도 크게 작용해요. 셀카에서 한쪽 눈만 작아 보인 경험 있으세요?"),
        ("참여형", "‘자연스러운 눈'이라는 말, 사실 사람마다 뜻이 달라요. 티 안 나는 눈인지, 또렷한데 과하지 않은 눈인지가 다르거든요. 여러분이 생각하는 자연스러움은 어느 쪽인가요?"),
        ("정보형", "쌍꺼풀 라인은 높을수록 또렷해 보이지만, 무조건 예뻐지는 건 아니에요. 눈꺼풀 두께와 눈 뜨는 힘이 안 맞으면 오히려 졸려 보일 수 있어요."),
        ("정보형", "매몰이 잘 맞는 눈은 따로 있어요. 피부가 너무 두껍지 않고, 처짐이 심하지 않고, 라인을 잡았을 때 버티는 힘이 있는 눈이에요. 그래서 방법보다 눈 상태가 먼저예요."),
        ("정보형", "눈재수술은 ‘전보다 크게'보다 ‘왜 마음에 안 들었는지'가 먼저예요. 소세지인지, 비대칭인지, 풀림인지 원인이 달라야 계획도 달라져요."),
        ("정보형", "앞트임은 많이 튼다고 시원해지는 수술이 아니에요. 몽고주름 방향, 눈 사이 거리, 흉터 가능성을 같이 봐야 해요. 과하면 되돌리기가 더 어렵습니다."),
        ("정보형", "남자 눈성형은 라인을 만드는 것보다 인상을 정리하는 쪽이 더 중요할 때가 많아요. 너무 진한 라인은 오히려 어색해 보일 수 있어요."),
        ("일상형", "마라톤을 하다 보면 초반 페이스가 제일 무섭다는 걸 느껴요. 수술도 비슷해요. 처음부터 욕심내기보다 내 눈에 맞는 속도와 방향을 잡는 게 오래 갑니다."),
        ("일상형", "어제는 강아지 산책시키고 책을 조금 읽었어요. 요즘 마케팅 공부도 하는데, 결국 진짜 오래 남는 건 과장보다 신뢰더라고요. 진료도 똑같다고 생각해요."),
    ]
    return [{"type": t, "text": _safe_short(x)} for t, x in items]

def _make_threads(date_str=None):
    date_str = date_str or _threads_today()
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    posts = []
    for idx, item in enumerate(_default_threads(), start=1):
        post_id = f"{date_str}_thread_{idx:02d}"
        text = item["text"]
        posts.append({
            "id": post_id,
            "date": date_str,
            "no": idx,
            "type": item["type"],
            "text": text,
            "length": len(text),
            "created_at": now,
            "persona": THREAD_PERSONA,
        })
    _thread_file(date_str).write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")
    return posts

def _get_threads(date_str):
    f = _thread_file(date_str)
    if not f.exists():
        return []
    try:
        posts = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        posts = []
    published = _load_threads_published()
    for p in posts:
        p["published"] = bool(published.get(p.get("id")))
        p["length"] = len(p.get("text", ""))
    return posts

def _thread_dates():
    THREADS_DIR.mkdir(parents=True, exist_ok=True)
    dates = sorted([f.stem for f in THREADS_DIR.glob("*.json") if f.stem.isdigit()], reverse=True)
    today = _threads_today()
    if today not in dates:
        dates.insert(0, today)
    return dates[:30]

@app.route('/threads')
def threads_page():
    return render_template_string(THREAD_HTML)

@app.route('/api/threads/data')
def api_threads_data():
    dates = _thread_dates()
    posts_by_date = {d: _get_threads(d) for d in dates}
    return jsonify({"dates": dates, "posts_by_date": posts_by_date})

@app.route('/api/threads/generate', methods=['POST'])
def api_threads_generate():
    try:
        date_str = _threads_today()
        _make_threads(date_str)
        return jsonify({"success": True, "date": date_str})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/threads/toggle', methods=['POST'])
def api_threads_toggle():
    data = request.get_json() or {}
    post_id = data.get('id')
    published = _load_threads_published()
    published[post_id] = not bool(published.get(post_id))
    _save_threads_published(published)
    return jsonify({"published": published[post_id]})




# ════════════════════════════════════════════
# AI 노출 점유율(SOV) API
# ════════════════════════════════════════════
SOV_DIR = BASE_DIR / "output" / "sov"

@app.route("/api/sov/report")
def api_sov_report():
    """오늘 SOV 인사이트 보고서 반환"""
    date_str = datetime.now().strftime("%Y%m%d")
    f = SOV_DIR / f"{date_str}_report.json"
    if f.exists():
        try:
            return jsonify(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return jsonify({"date": date_str, "summary_text": "", "golden_prompt": "", "content_strategy": ""})


@app.route("/api/sov/today")
def api_sov_today():
    date_str = datetime.now().strftime("%Y%m%d")
    f = SOV_DIR / f"{date_str}.json"
    if f.exists():
        try:
            return jsonify(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return jsonify({"date": date_str, "summary": {"sov_pct": 0, "our_mentions": 0, "total_prompts": 0}, "industry_ranking": [], "top_ai_keywords": [], "category_sov": {}})

@app.route("/api/sov/history")
def api_sov_history():
    days = int(request.args.get("days", 10))
    files = sorted(SOV_DIR.glob("*.json"), reverse=True)[:days] if SOV_DIR.exists() else []
    history = []
    for f in reversed(list(files)):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            row = {"date": d["date"],
                   "overall_sov_pct": d["summary"].get("overall_sov_pct", d["summary"].get("sov_pct", 0)),
                   "total_prompts": d["summary"].get("total_prompts", 0)}
            for mid, ms in d.get("models", {}).items():
                row[f"{mid}_sov"] = ms.get("sov_pct", 0)
                row[f"{mid}_rank"] = ms.get("our_rank")
            history.append(row)
        except Exception:
            continue
    return jsonify(history)

@app.route("/api/sov/measure", methods=["POST"])
def api_sov_measure():
    import subprocess as _sp
    try:
        force = request.json.get("force", False) if request.json else False

        # Step 1: 프롬프트 파일 없으면 자동 생성
        date_str = datetime.now().strftime("%Y%m%d")
        prompt_file = BASE_DIR / "output" / "prompts" / f"{date_str}.json"
        if not prompt_file.exists() or force:
            print(f"[SOV] 프롬프트 생성 중...", flush=True)
            r1 = _sp.run(
                ["python", "prompt_gen.py"] + (["--force"] if force else []),
                cwd=str(BASE_DIR), capture_output=True, text=True, timeout=120
            )
            if r1.returncode != 0:
                return jsonify({"success": False, "error": "프롬프트 생성 실패: " + r1.stderr[-500:]})

        # Step 2: SOV 측정
        print(f"[SOV] 측정 시작...", flush=True)
        cmd = ["python", "sov_tracker.py"] + (["--force"] if force else [])
        result = _sp.run(cmd, cwd=str(BASE_DIR), capture_output=True, text=True, timeout=600)

        f = SOV_DIR / f"{date_str}.json"
        if f.exists():
            data = json.loads(f.read_text(encoding="utf-8"))
            return jsonify({"success": True, "data": data})
        return jsonify({"success": False, "error": result.stderr[-1000:]})
    except _sp.TimeoutExpired:
        return jsonify({"success": False, "error": "측정 시간 초과 (10분)"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ════════════════════════════════════════════
# 오늘의 추천 프롬프트 API
# ════════════════════════════════════════════
PROMPT_DIR = BASE_DIR / "output" / "prompts"

@app.route("/api/prompts/today")
def api_prompts_today():
    import subprocess as _sp
    date_str = datetime.now().strftime("%Y%m%d")
    out_file = PROMPT_DIR / f"{date_str}.json"

    # 없으면 자동 생성
    if not out_file.exists():
        try:
            _sp.run(["python", "prompt_gen.py"], cwd=str(BASE_DIR),
                    capture_output=True, text=True, timeout=60)
        except Exception:
            pass

    if out_file.exists():
        try:
            return jsonify(json.loads(out_file.read_text(encoding="utf-8")))
        except Exception:
            pass
    return jsonify({"date": date_str, "total": 0, "prompts": []})


@app.route("/api/prompts/generate", methods=["POST"])
def api_prompts_generate():
    import subprocess as _sp
    try:
        result = _sp.run(
            ["python", "prompt_gen.py", "--force"],
            cwd=str(BASE_DIR), capture_output=True, text=True, timeout=60
        )
        date_str = datetime.now().strftime("%Y%m%d")
        out_file = PROMPT_DIR / f"{date_str}.json"
        if out_file.exists():
            data = json.loads(out_file.read_text(encoding="utf-8"))
            return jsonify({"success": True, "total": data["total"], "prompts": data["prompts"]})
        return jsonify({"success": False, "error": result.stderr})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


SOV_PAGE_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>노출 점유율 - 팝성형외과</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI','Noto Sans KR',sans-serif;background:#f0f2f5;color:#1a1a2e}
.nav{background:#1a1a2e;display:flex;padding:0 24px;position:sticky;top:0;z-index:100}
.nav a{padding:13px 20px;font-size:13px;color:#a0a0c0;text-decoration:none;border-bottom:3px solid transparent;display:block}
.nav a:hover{color:#a78bfa}.nav a.on{color:#a78bfa;border-bottom-color:#a78bfa}
.header{background:linear-gradient(135deg,#1a1a2e,#16213e);color:#fff;padding:24px 40px;display:flex;align-items:center;justify-content:space-between}
.header h1{font-size:20px;font-weight:700}
.header p{font-size:13px;color:#8888aa;margin-top:4px}
.hbtns{display:flex;gap:8px}
.hbtn{padding:9px 18px;border-radius:8px;font-size:13px;font-weight:600;border:none;cursor:pointer}
.hbtn.primary{background:#a78bfa;color:#fff}
.hbtn.sec{background:rgba(255,255,255,.12);color:#fff}
.wrap{max-width:1200px;margin:0 auto;padding:28px 24px}
.tabs{display:flex;gap:4px;background:#fff;border-radius:10px;padding:4px;box-shadow:0 2px 8px rgba(0,0,0,.06);margin-bottom:24px;width:fit-content}
.tab{padding:8px 20px;border-radius:7px;font-size:13px;font-weight:500;cursor:pointer;border:none;background:transparent;color:#6b7280}
.tab.on{background:#1a1a2e;color:#fff}
.panel{display:none}.panel.on{display:block}
/* SOV 패널 */
.sov-hero{background:#fff;border-radius:14px;padding:28px 32px;box-shadow:0 2px 10px rgba(0,0,0,.06);margin-bottom:20px;display:flex;align-items:center;gap:40px;flex-wrap:wrap}
.sov-big{font-size:56px;font-weight:800;color:#1a1a2e;line-height:1}
.sov-lbl{font-size:13px;color:#9ca3af;margin-top:6px}
.model-cards{display:flex;gap:16px;flex:1;flex-wrap:wrap}
.mcard{background:#f8f9ff;border:1px solid #e8eaf6;border-radius:12px;padding:18px 22px;text-align:center;min-width:140px;flex:1}
.mcard .mv{font-size:28px;font-weight:800;color:#1a1a2e}
.mcard .mn{font-size:12px;color:#9ca3af;margin-top:4px}
.mcard .mr{font-size:12px;color:#a78bfa;margin-top:3px;font-weight:600}
.mcard.has{background:#f0f4ff;border-color:#c7d2fe}
/* 히스토리 그래프 */
.chart-wrap{background:#fff;border-radius:14px;padding:24px 28px;box-shadow:0 2px 10px rgba(0,0,0,.06);margin-bottom:20px}
.chart-title{font-size:15px;font-weight:700;margin-bottom:4px}
.chart-sub{font-size:12px;color:#9ca3af;margin-bottom:20px}
.bars{display:flex;align-items:flex-end;gap:6px;height:120px;padding-bottom:0}
.bar-wrap{display:flex;flex-direction:column;align-items:center;gap:4px;flex:1}
.bar{width:100%;border-radius:4px 4px 0 0;background:#c7d2fe;transition:height .3s;min-height:2px;cursor:pointer;position:relative}
.bar:hover{background:#a78bfa}
.bar-val{font-size:10px;color:#6b7280}
.bar-date{font-size:10px;color:#9ca3af;transform:rotate(-30deg);white-space:nowrap}
/* Industry Ranking */
.ranking{background:#fff;border-radius:14px;padding:24px 28px;box-shadow:0 2px 10px rgba(0,0,0,.06);margin-bottom:20px}
.rank-row{display:flex;align-items:center;padding:10px 0;border-bottom:1px solid #f3f4f6;gap:12px}
.rank-row:last-child{border-bottom:none}
.rank-num{font-size:16px;font-weight:700;color:#9ca3af;min-width:28px}
.rank-num.top3{color:#1a1a2e}
.rank-name{font-size:14px;font-weight:600;flex:1}
.rank-name.ours{color:#a78bfa}
.rank-bar{height:6px;background:#e5e7eb;border-radius:3px;flex:2;overflow:hidden}
.rank-fill{height:100%;background:#c7d2fe;border-radius:3px;transition:width .5s}
.rank-fill.ours{background:#a78bfa}
.rank-pct{font-size:13px;font-weight:700;color:#6b7280;min-width:48px;text-align:right}
/* 프롬프트 패널 */
.prompt-list{display:flex;flex-direction:column;gap:10px}
.prompt-card{background:#fff;border-radius:12px;padding:16px 20px;box-shadow:0 2px 8px rgba(0,0,0,.06);display:flex;gap:14px;align-items:flex-start}
.pcat{font-size:11px;padding:3px 9px;border-radius:20px;font-weight:600;white-space:nowrap}
.pcat.eye{background:#e8f0fe;color:#4f8ef7}
.pcat.lifting{background:#fff0e8;color:#f7934f}
.pcat.nose{background:#e8faf3;color:#4fd19e}
.ptext{font-size:14px;color:#1a1a2e;line-height:1.5;flex:1}
.pkw{font-size:12px;color:#9ca3af;margin-top:4px}
.psrc{font-size:11px;color:#a78bfa;margin-top:2px}
/* 키워드 패널 */
.kw-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px}
.kw-card{background:#fff;border-radius:12px;padding:14px 18px;box-shadow:0 2px 8px rgba(0,0,0,.06);display:flex;align-items:center;justify-content:space-between}
.kw-text{font-size:14px;font-weight:600;color:#1a1a2e}
.kw-cnt{font-size:12px;background:#f3f0ff;color:#7c5fe6;padding:3px 9px;border-radius:20px;font-weight:700}
.empty{text-align:center;padding:60px;color:#9ca3af;font-size:14px}
.loading{text-align:center;padding:40px;color:#9ca3af}
.model-detail{display:flex;gap:16px;margin-bottom:20px;flex-wrap:wrap}
.md-card{background:#fff;border-radius:12px;padding:18px 22px;flex:1;min-width:200px;box-shadow:0 2px 8px rgba(0,0,0,.06)}
.md-title{font-size:12px;color:#9ca3af;margin-bottom:8px;font-weight:600;letter-spacing:.05em}
.md-rank-row{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f3f4f6;font-size:13px}
.md-rank-row:last-child{border-bottom:none}
.md-brand.ours{color:#a78bfa;font-weight:700}
</style>
</head>
<body>
<div class="nav">
  <a href="/">홈</a>
  <a href="/blog">블로그</a>
  <a href="/youtube">유튜브</a>
  <a href="/magazine">매거진</a>
  <a href="/cardnews">카드뉴스</a>
  <a href="/threads">스레드</a>
  <a href="/sov" class="on">노출 점유율</a>
</div>
<div class="header">
  <div>
    <h1>노출 점유율 (Share of Voice)</h1>
    <p>AI 대화 결과에서 팝성형외과가 얼마나 추천되고 있는지 확인하세요</p>
  </div>
  <div class="hbtns">
    <button class="hbtn sec" onclick="loadAll()">새로고침</button>
    <button class="hbtn primary" id="measureBtn" onclick="measure()">▶ 지금 측정</button>
  </div>
</div>
<div class="wrap">
  <div class="tabs">
    <button class="tab on" onclick="switchTab('sov',this)">노출 점유율</button>
    <button class="tab" onclick="switchTab('report',this)">📋 인사이트 보고서</button>
    <button class="tab" onclick="switchTab('prompts',this)">프롬프트</button>
    <button class="tab" onclick="switchTab('keywords',this)">AI 검색 키워드</button>
    <button class="tab" onclick="switchTab('ranking',this)">경쟁사 랭킹</button>
  </div>

  <!-- SOV 패널 -->
  <div class="panel on" id="panel-sov">
    <div class="sov-hero">
      <div>
        <div class="sov-big" id="sovBig">--%</div>
        <div class="sov-lbl">Share of Voice (전체)</div>
      </div>
      <div class="model-cards" id="modelCards">
        <div class="loading">측정 데이터 로딩 중...</div>
      </div>
    </div>
    <div class="chart-wrap">
      <div class="chart-title">최근 10일 SOV 추이</div>
      <div class="chart-sub">날짜별 전체 노출 점유율</div>
      <div class="bars" id="histBars"><div class="loading">히스토리 로딩 중...</div></div>
    </div>
    <div class="model-detail" id="modelDetail"></div>
  </div>

  <!-- 인사이트 보고서 패널 -->
  <div class="panel" id="panel-report">
    <div id="reportWrap" style="display:flex;flex-direction:column;gap:16px">
      <div class="loading">보고서 로딩 중...</div>
    </div>
  </div>

  <!-- 프롬프트 패널 -->
  <div class="panel" id="panel-prompts">
    <div class="prompt-list" id="promptList">
      <div class="loading">프롬프트 로딩 중...</div>
    </div>
  </div>

  <!-- AI 검색 키워드 패널 -->
  <div class="panel" id="panel-keywords">
    <div class="kw-grid" id="kwGrid">
      <div class="loading">키워드 로딩 중...</div>
    </div>
  </div>

  <!-- 경쟁사 랭킹 패널 -->
  <div class="panel" id="panel-ranking">
    <div class="ranking" id="rankingList">
      <div class="loading">랭킹 로딩 중...</div>
    </div>
  </div>
</div>

<script>
const CLABEL = {eye:'눈성형',lifting:'리프팅',nose:'코성형'};
const MLABEL = {perplexity:'Perplexity',gemini:'Gemini',chatgpt:'ChatGPT'};
let sovData = null, histData = [], promptData = null;

function switchTab(id, btn) {
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('on'));
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('on'));
  btn.classList.add('on');
  document.getElementById('panel-'+id).classList.add('on');
}

async function loadSOV() {
  const r = await fetch('/api/sov/today');
  sovData = await r.json();
  renderSOV();
}

async function loadHistory() {
  const r = await fetch('/api/sov/history?days=10');
  histData = await r.json();
  renderHistory();
}

async function loadPrompts() {
  const r = await fetch('/api/prompts/today');
  promptData = await r.json();
  renderPrompts();
  renderKeywords();
}

async function loadReport() {
  try {
    const r = await fetch('/api/sov/report');
    const d = await r.json();
    const wrap = document.getElementById('reportWrap');
    if (!d.overall_summary && !d.summary_text) {
      wrap.innerHTML = '<div class="empty" style="text-align:center;padding:60px;color:#9ca3af">측정 후 보고서가 자동 생성돼요.<br>측정 버튼을 눌러주세요.</div>';
      return;
    }
    const pct = d.overall_sov_pct || 0;
    wrap.innerHTML = `
      <div class="report-card">
        <div class="report-badge badge-sov">📊 전체 SOV ${d.overall_sov_pct||0}%</div>
        <div class="report-title">AI 검색 점유율 진단 결과</div>
        <div class="report-body">${d.overall_summary||''}</div>
      </div>
      <div class="report-card">
        <div class="report-badge badge-ok">✅ 강점 (Success Pattern)</div>
        <div class="report-body">${d.strength_pattern||''}</div>
      </div>
      <div class="report-card">
        <div class="report-badge badge-warn">⚠ 보완점 (Avoidance Pattern)</div>
        <div class="report-body">${d.weakness_pattern||''}</div>
      </div>
      <div class="golden-box">
        <div class="report-badge badge-gold">🎯 오늘의 추천 프롬프트 (Golden Prompt)</div>
        <div class="golden-prompt">"${d.golden_prompt||''}"</div>
        <div class="report-body">${d.golden_prompt_reason||''}</div>
        <button class="copy-btn" onclick="navigator.clipboard.writeText('${(d.golden_prompt||'').replace(/'/g,'\\\'')}')">복사하기</button>
      </div>
      <div class="report-card">
        <div class="report-badge badge-warn">📝 콘텐츠 전략 가이드</div>
        <div class="report-body">${d.content_strategy||''}</div>
      </div>
      <div class="next-step">
        <strong>🚀 Next Step:</strong> ${d.next_step||''}
      </div>
    `;
  } catch(e) {
    document.getElementById('reportWrap').innerHTML = '<div class="empty">보고서 로드 실패</div>';
  }
}

async function loadAll() {
  await Promise.all([loadSOV(), loadHistory(), loadPrompts(), loadReport()]);
  renderWeekCalendar();
  renderGuideProgress();
}

function renderWeekCalendar() {
  const days = ['일','월','화','수','목','금','토'];
  const today = new Date();
  const monday = new Date(today);
  monday.setDate(today.getDate() - (today.getDay() === 0 ? 6 : today.getDay() - 1));

  // 주간 레이블
  const endDate = new Date(monday); endDate.setDate(monday.getDate() + 6);
  const fmt = d => `${d.getMonth()+1}/${d.getDate()}`;
  const wl = document.getElementById('week-label');
  if (wl) wl.textContent = `이번 주  ${fmt(monday)} – ${fmt(endDate)}`;

  // 자동화 스케줄
  const schedule = {
    1: [{time:'09:00', label:'주간 SoV 모니터링'}, {time:'09:00', label:'Citation 트렌드 분석'}],
    2: [{time:'09:00', label:'GEO 콘텐츠 작성'}],
    3: [],
    4: [{time:'09:00', label:'GEO 콘텐츠 작성'}],
    5: [],
    6: [{time:'09:00', label:'GEO 콘텐츠 작성'}],
    0: [],
  };

  const cal = document.getElementById('week-calendar');
  if (!cal) return;
  cal.innerHTML = '';

  for (let i = 0; i < 7; i++) {
    const d = new Date(monday); d.setDate(monday.getDate() + i);
    const dayIdx = d.getDay();
    const isToday = d.toDateString() === today.toDateString();
    const tasks = schedule[dayIdx] || [];
    const isPast = d < today && !isToday;

    cal.innerHTML += `
      <div style="border:1px solid ${isToday?'#a78bfa':'#f3f4f6'};border-radius:10px;padding:10px;background:${isToday?'#f5f3ff':'#fff'};min-height:120px">
        <div style="font-size:12px;font-weight:${isToday?'700':'500'};color:${isToday?'#a78bfa':'#6b7280'};margin-bottom:8px">${days[dayIdx]} ${d.getDate()}</div>
        ${tasks.length ? tasks.map(t=>`
          <div style="background:#f0fdf4;border-radius:6px;padding:6px 8px;margin-bottom:4px;font-size:11px">
            <div style="color:#9ca3af;margin-bottom:2px">${t.time} 🔒 미리보기</div>
            <div style="font-weight:600;color:#1a1a2e">${t.label}</div>
          </div>`).join('') : '<div style="color:#e5e7eb;font-size:11px;text-align:center;padding-top:20px">-</div>'}
      </div>`;
  }
}

async function runAutoPipeline() {
  const btn = document.getElementById('auto-run-btn');
  const statusBox = document.getElementById('auto-pipeline-status');
  btn.disabled = true;
  btn.textContent = '⏳ 실행 중...';
  statusBox.style.display = 'block';

  try {
    await fetch('/api/auto/run', {method:'POST', headers:{'Content-Type':'application/json'}});
    // 폴링으로 상태 확인
    const poll = setInterval(async () => {
      const r = await fetch('/api/auto/status');
      const d = await r.json();
      const steps = d.steps || {};
      updateStepUI('step1_sov', 'status-step1', 'icon-step1', steps.step1_sov);
      updateStepUI('step2_content', 'status-step2', 'icon-step2', steps.step2_content);
      updateStepUI('step3_publish', 'status-step3', 'icon-step3', steps.step3_publish);

      const allDone = ['step1_sov','step2_content','step3_publish']
        .every(k => steps[k]?.status === 'done' || steps[k]?.status === 'error');
      if (allDone) {
        clearInterval(poll);
        btn.disabled = false;
        btn.textContent = '✅ 완료! 다시 실행';
      }
    }, 3000);
  } catch(e) {
    btn.disabled = false;
    btn.textContent = '🔄 자동화 한 번에 실행';
    alert('오류: ' + e.message);
  }
}

function updateStepUI(key, elId, iconId, step) {
  if (!step) return;
  const el = document.getElementById(elId);
  const icon = document.getElementById(iconId);
  if (!el || !icon) return;
  if (step.status === 'running') {
    icon.textContent = '⏳'; el.style.color = '#a78bfa';
  } else if (step.status === 'done') {
    icon.textContent = '✅'; el.style.color = '#16a34a';
  } else if (step.status === 'error') {
    icon.textContent = '❌'; el.style.color = '#ef4444';
  } else {
    icon.textContent = '○'; el.style.color = '#9ca3af';
  }
}

function renderGuideProgress() {
  // 홈 페이지에만 있는 요소 - null 체크
  const el = document.getElementById('guide-progress-text');
  if (!el) return;
  const steps = document.querySelectorAll('.guide-step');
  let doneCount = 0;
  steps.forEach((s,i) => {
    if (s.classList.contains('done')) doneCount++;
  });
  const total = steps.length;
  el.textContent = `${doneCount+1} / ${total} 단계 진행 중`;
}

function renderSOV() {
  if (!sovData) return;
  const s = sovData.summary || {};
  const measured = (s.total_prompts || 0) > 0;
  const pct = s.overall_sov_pct ?? s.sov_pct ?? 0;
  document.getElementById('sovBig').textContent = measured ? pct+'%' : '--%';

  const models = sovData.models || {};
  const mc = document.getElementById('modelCards');
  if (Object.keys(models).length) {
    mc.innerHTML = Object.entries(models).map(([k,m]) => {
      const hasData = m.measured > 0;
      const rank = m.our_rank ? '#'+m.our_rank+'위' : (hasData ? '미언급' : '');
      return `<div class="mcard ${hasData&&m.our_mentions>0?'has':''}">
        <div class="mv">${hasData ? m.sov_pct+'%' : '미측정'}</div>
        <div class="mn">${MLABEL[k]||k}</div>
        <div class="mr">${rank}</div>
      </div>`;
    }).join('');
  } else {
    mc.innerHTML = '<div style="color:#9ca3af;font-size:13px">측정 버튼을 눌러주세요</div>';
  }

  // 모델별 상세 랭킹
  const md = document.getElementById('modelDetail');
  if (Object.keys(models).length) {
    md.innerHTML = Object.entries(models).map(([k,m]) => {
      const top5 = (m.ranking||[]).slice(0,5);
      return `<div class="md-card">
        <div class="md-title">${MLABEL[k]||k} Top 5</div>
        ${top5.map((r,i)=>`<div class="md-rank-row">
          <span class="md-brand ${r.brand==='팝성형외과'?'ours':''}">${i+1}. ${r.brand}</span>
          <span style="color:#9ca3af">${r.pct}%</span>
        </div>`).join('')}
      </div>`;
    }).join('');
  }

  // 랭킹
  renderRanking();
}

function renderHistory() {
  const el = document.getElementById('histBars');
  if (!histData.length) { el.innerHTML='<div class="empty">히스토리 없음</div>'; return; }
  const max = Math.max(...histData.map(d=>d.overall_sov_pct||0), 1);
  el.innerHTML = histData.map(d => {
    const pct = d.overall_sov_pct || 0;
    const h = Math.max(Math.round((pct/max)*110), 2);
    const date = d.date ? d.date.slice(4,6)+'/'+d.date.slice(6,8) : '';
    return `<div class="bar-wrap">
      <div class="bar-val">${pct}%</div>
      <div class="bar" style="height:${h}px" title="${date}: ${pct}%"></div>
      <div class="bar-date">${date}</div>
    </div>`;
  }).join('');
}

function renderPrompts() {
  const el = document.getElementById('promptList');
  const ps = (promptData?.prompts || []);
  if (!ps.length) { el.innerHTML='<div class="empty">프롬프트가 없어요. 측정 버튼을 눌러주세요.</div>'; return; }
  el.innerHTML = ps.map(p => `
    <div class="prompt-card">
      <span class="pcat ${p.category||''}">${CLABEL[p.category]||p.category||''}</span>
      <div>
        <div class="ptext">${p.prompt}</div>
        <div class="pkw">타깃 키워드: ${p.target_keyword||'-'}</div>
        ${p.reverse_from ? `<div class="psrc">역추적: ${p.reverse_from}</div>` : ''}
      </div>
    </div>`).join('');
}

function renderKeywords() {
  const el = document.getElementById('kwGrid');
  const kws = (sovData?.top_ai_keywords || []);
  // SOV 없으면 프롬프트 키워드라도
  const fallback = (promptData?.prompts||[]).map(p=>({keyword:p.target_keyword,count:1})).filter(k=>k.keyword);
  const list = kws.length ? kws : fallback;
  if (!list.length) { el.innerHTML='<div class="empty">측정 후 키워드가 집계돼요</div>'; return; }
  el.innerHTML = list.map(k=>`
    <div class="kw-card">
      <span class="kw-text">${k.keyword}</span>
      <span class="kw-cnt">${k.count}회</span>
    </div>`).join('');
}

function renderRanking() {
  const el = document.getElementById('rankingList');
  const ranking = (sovData?.industry_ranking || []);
  if (!ranking.length) { el.innerHTML='<div class="empty">측정 후 랭킹이 집계돼요</div>'; return; }
  const max = Math.max(...ranking.map(r=>r.total_count||r.count||0), 1);
  el.innerHTML = ranking.map((r,i) => {
    const cnt = r.total_count || r.count || 0;
    const pct = r.pct || 0;
    const isOurs = r.brand === '팝성형외과';
    const w = Math.round((cnt/max)*100);
    return `<div class="rank-row">
      <div class="rank-num ${i<3?'top3':''}">${i+1}</div>
      <div class="rank-name ${isOurs?'ours':''}">${r.brand}${isOurs?' <- 우리':''}</div>
      <div class="rank-bar"><div class="rank-fill ${isOurs?'ours':''}" style="width:${w}%"></div></div>
      <div class="rank-pct">${pct}%</div>
    </div>`;
  }).join('');
}

async function measure() {
  const btn = document.getElementById('measureBtn');
  btn.disabled=true; btn.textContent='측정 중...';
  try {
    const r = await fetch('/api/sov/measure',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({force:false})});
    const d = await r.json();
    if (d.success) { await loadAll(); }
    else alert('측정 실패: '+(d.error||''));
  } catch(e) { alert('오류: '+e.message); }
  finally { btn.disabled=false; btn.textContent='▶ 지금 측정'; }
}

loadAll();
</script>
</body>
</html>
"""

@app.route('/sov')
def sov_page():
    return render_template_string(SOV_PAGE_HTML)


# ════════════════════════════════════════════
# 유튜브 스크립트 저장/조회 API
# ════════════════════════════════════════════
YT_SCRIPT_DIR = BASE_DIR / "output" / "yt_scripts"
YT_SCRIPT_DIR.mkdir(parents=True, exist_ok=True)

@app.route("/api/yt_scripts/save", methods=["POST"])
def api_yt_scripts_save():
    """Lovable/n8n에서 생성된 스크립트 저장"""
    try:
        data = request.get_json() or {}
        date_str = datetime.now().strftime("%Y%m%d")
        ts = datetime.now().strftime("%H%M%S")
        category = data.get("category", "unknown")
        fname = f"{date_str}_{ts}_{category}.json"
        out = YT_SCRIPT_DIR / fname
        data["saved_at"] = datetime.now().isoformat()
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return jsonify({"success": True, "filename": fname})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/yt_scripts/list")
def api_yt_scripts_list():
    """저장된 스크립트 목록 반환"""
    try:
        files = sorted(YT_SCRIPT_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        scripts = []
        for f in files[:50]:
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                scripts.append({
                    "filename": f.name,
                    "date": d.get("saved_at", "")[:10],
                    "category": d.get("category", ""),
                    "type": d.get("type", ""),
                    "keywords": d.get("keywords", []),
                    "title_seo": (d.get("titles") or {}).get("seo", ""),
                    "longform_preview": (d.get("longform") or "")[:100],
                })
            except Exception:
                continue
        return jsonify(scripts)
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/api/yt_scripts/get/<filename>")
def api_yt_scripts_get(filename):
    """특정 스크립트 전체 내용 반환"""
    try:
        f = YT_SCRIPT_DIR / filename
        if not f.exists():
            return jsonify({"error": "파일 없음"}), 404
        return jsonify(json.loads(f.read_text(encoding="utf-8")))
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/api/yt_scripts/delete/<filename>", methods=["DELETE"])
def api_yt_scripts_delete(filename):
    """스크립트 삭제"""
    try:
        f = YT_SCRIPT_DIR / filename
        if f.exists():
            f.unlink()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ════════════════════════════════════════════
# 콘텐츠 AI 페이지 - 유튜브 스크립트 + 얼굴형 분석 + 키워드 릴스
# ════════════════════════════════════════════

CONTENT_AI_DIR = BASE_DIR / "output" / "content_ai"
CONTENT_AI_DIR.mkdir(parents=True, exist_ok=True)

import base64 as _base64

# -- API 라우트 ----------------------------------------------------


# 29가지 콘텐츠 각도 목록
CONTENT_ANGLES = [
    {"angle": "오해와 진실", "desc": "많은 사람들이 잘못 알고 있는 상식을 바로잡는 영상"},
    {"angle": "비교와 선택", "desc": "두 가지 이상의 옵션을 비교해 선택 기준을 제시"},
    {"angle": "주의사항", "desc": "수술/시술 전후 꼭 알아야 할 주의점"},
    {"angle": "회복과 관리", "desc": "수술 후 회복 과정과 올바른 관리 방법"},
    {"angle": "타이밍과 시기", "desc": "언제 하면 좋은지, 나이/계절/상황별 적절한 시기"},
    {"angle": "심리와 감정", "desc": "수술 전후 환자가 느끼는 불안, 기대, 변화 심리"},
    {"angle": "후회와 재수술", "desc": "잘못된 선택으로 인한 후회와 재수술 사례"},
    {"angle": "나이와 노화", "desc": "나이에 따른 차이, 노화와 성형의 관계"},
    {"angle": "원장 시각", "desc": "의사 입장에서 솔직하게 말하는 비하인드"},
    {"angle": "케이스 분석", "desc": "특정 케이스를 심층 분석하는 사례 중심"},
    {"angle": "숫자와 데이터", "desc": "통계, 수치, 데이터로 설명하는 팩트 기반"},
    {"angle": "원인과 메커니즘", "desc": "왜 그렇게 되는지 원리와 메커니즘 설명"},
    {"angle": "Q&A 답변", "desc": "환자들이 자주 묻는 질문에 답변하는 형식"},
    {"angle": "전후 변화", "desc": "수술 전후 변화 과정을 단계별로 설명"},
    {"angle": "부작용과 위험", "desc": "부작용, 위험성, 실패 케이스 솔직 공개"},
    {"angle": "비용과 가격", "desc": "가격 범위, 비용 대비 효과 분석"},
    {"angle": "트렌드 분석", "desc": "최근 성형 트렌드, 유행하는 스타일 분석"},
    {"angle": "유명인 분석", "desc": "연예인/인플루언서 얼굴 변화 분석"},
    {"angle": "하면 안 되는 경우", "desc": "이런 사람은 수술하면 안 된다는 역발상"},
    {"angle": "자연스러움의 기준", "desc": "자연스러운 성형이란 무엇인지 기준 제시"},
    {"angle": "병원 선택 기준", "desc": "좋은 병원/의사 선택하는 방법"},
    {"angle": "회의와 고민", "desc": "수술을 고민하는 사람들에게 진심 어린 조언"},
    {"angle": "오래된 방식 vs 새 방식", "desc": "구식 vs 최신 기술/방법 비교"},
    {"angle": "외국과 한국 비교", "desc": "해외와 한국 성형 문화/기술 차이"},
    {"angle": "셀프 케어", "desc": "수술 없이 할 수 있는 자가 관리 방법"},
    {"angle": "시즌별 가이드", "desc": "봄여름가을겨울 계절별 성형/관리 가이드"},
    {"angle": "직업별 고려사항", "desc": "직업, 라이프스타일에 따른 성형 선택"},
    {"angle": "가족/주변 반응", "desc": "수술 후 가족, 친구, 직장 동료 반응 대처"},
    {"angle": "처음 하는 사람 가이드", "desc": "성형 처음 고려하는 사람을 위한 입문 가이드"},
]

def get_next_angle(category):
    """이미 생성된 각도를 제외하고 다음 각도 반환"""
    used_angles = []
    if CONTENT_AI_DIR.exists():
        for f in CONTENT_AI_DIR.glob(f"*_youtube_{category}*.json"):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                angle = d.get("angle", "")
                if angle:
                    used_angles.append(angle)
            except Exception:
                pass

    # 사용 안 한 각도 중 랜덤 선택
    import random
    available = [a for a in CONTENT_ANGLES if a["angle"] not in used_angles]
    if not available:
        available = CONTENT_ANGLES  # 다 썼으면 처음부터

    return random.choice(available)


@app.route("/api/content_ai/youtube", methods=["POST"])
def api_content_ai_youtube():
    # 유튜브 스크립트 생성 - 3단계 분리 방식
    try:
        import anthropic as _ant
        data = request.get_json() or {}
        category = data.get("category", "눈성형")
        vtype = data.get("type", "롱폼")

        # 각도 자동 선택 (중복 방지)
        angle_data = get_next_angle(category)
        angle = angle_data["angle"]
        angle_desc = angle_data["desc"]

        yt_keywords = []
        yt_key = os.environ.get("YOUTUBE_API_KEY", "")
        if yt_key:
            try:
                import urllib.request as _ur, urllib.parse as _up
                params = _up.urlencode({"part":"snippet","chart":"mostPopular","regionCode":"KR","maxResults":"10","key":yt_key})
                req = _ur.urlopen(f"https://www.googleapis.com/youtube/v3/videos?{params}", timeout=5)
                items = json.loads(req.read().decode())["items"]
                yt_keywords = [i["snippet"]["title"] for i in items[:3]]
            except Exception:
                pass

        client = _ant.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY",""))

        # STEP 1: 롱폼 대본 생성 (텍스트)
        longform_prompt = f"""팝성형외과 유튜브 {vtype} 스크립트를 작성해줘.
카테고리: {category}
이번 각도: {angle} ({angle_desc})
트렌딩: {", ".join(yt_keywords) if yt_keywords else "없음"}

[이번 영상 각도 - 반드시 이 각도로만 작성]
각도 "{angle}"의 관점에서 {category} 주제를 다루는 영상.
예: "오해와 진실" 각도면 "{category}에 대한 잘못된 상식", "하면 안 되는 경우" 각도면 "{category} 피해야 할 케이스"

[인기 유튜브 벤치마킹 적용]
후킹: 첫 문장에 핵심 결론 바로. 역설/반전 사용. 인사 7초 이내.
구조: 케이스 1->2->3 번호. 원장 자기 얼굴 직접 가리키며 설명. 마지막 요약.
톤: "솔직히 말하면" "사실은" "대부분 동의할 거예요" 활용. 단점도 솔직히.
리듬: 짧은문장 + 짧은문장 + 긴설명. 질문 - 바로 답.

[의료법] 효과보장/전후비교/최상급/타병원비교 금지. 부작용 언급 필수.

[기본 규칙]
- 해요체, 친근한 전문의 말투
- 문장마다 / 로 끊음
- 인사: 안녕하세요, 팝성형외과 000 원장입니다.
- 마무리: 지금까지 팝성형외과 000 원장이었습니다.
- 마지막: *본 콘텐츠는 AI 기반 도구의 도움을 받아 제작되었으며, 진단치료를 대체하지 않습니다.
- {"3분 분량 약 1000~1200자" if "롱폼" in vtype else "30초 분량 약 200자"}

형식:
[0:00 후킹]
[0:15 인사]
[0:25 본론]
[2:30 마무리]

스크립트만 출력."""


        resp1 = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=3000,
            messages=[{"role":"user","content":longform_prompt}]
        )
        longform_text = resp1.content[0].text.strip()

        # STEP 2: 메타데이터 생성 (간단한 JSON)
        meta_prompt = f"""스크립트 메타데이터를 JSON으로만 출력해줘.
번역은 현지인이 실제로 쓰는 자연스러운 표현으로. 직역 금지.

카테고리: {category}
각도: {angle}
스크립트 앞부분: {longform_text[:300]}

JSON (다른 텍스트 없이):
{{
  "keywords": ["키워드1", "키워드2", "키워드3"],
  "title_seo": "SEO형 제목 (한국어)",
  "title_curiosity": "궁금증형 제목 (한국어)",
  "title_empathy": "공감형 제목 (한국어)",
  "thumbnail1": "썸네일 문구1",
  "thumbnail2": "썸네일 문구2",
  "thumbnail3": "썸네일 문구3",
  "hook1": "첫3초자막1 (12자이내)",
  "hook2": "첫3초자막2 (12자이내)",
  "hook3": "첫3초자막3 (12자이내)",
  "hashtags": "#태그1 #태그2 #태그3 #태그4 #태그5 #태그6 #태그7 #태그8 #태그9 #태그10",
  "description": "SEO 설명 2줄",
  "en": {{
    "title": "영어 제목 (자연스러운 영어, YouTube 현지 사용자 기준)",
    "thumbnail": "영어 썸네일 문구 (임팩트 있게)",
    "hashtags": "#EnglishTag1 #EnglishTag2 #EnglishTag3 #EnglishTag4 #EnglishTag5"
  }},
  "zh": {{
    "title": "중국어 제목 (간체자, 중국 현지 SNS 감성)",
    "thumbnail": "중국어 썸네일 문구",
    "hashtags": "#中文标签1 #中文标签2 #中文标签3 #中文标签4 #中文标签5"
  }},
  "ja": {{
    "title": "일본어 제목 (자연스러운 일본어, 일본 유튜브 감성)",
    "thumbnail": "일본어 썸네일 문구",
    "hashtags": "#日本語タグ1 #日本語タグ2 #日本語タグ3 #日本語タグ4 #日本語タグ5"
  }}
}}"""

        resp2 = client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=800,
            messages=[{"role":"user","content":meta_prompt}]
        )
        meta_raw = resp2.content[0].text.strip().replace("```json","").replace("```","").strip()
        if "{" in meta_raw:
            meta_raw = meta_raw[meta_raw.find("{"):meta_raw.rfind("}")+1]
        try:
            meta = json.loads(meta_raw)
        except Exception:
            meta = {}

        # STEP 3: 숏폼 4개 추출 (롱폼 전체 기반)
        shorts_prompt = f"""아래 롱폼 스크립트에서 30초 숏폼 4개를 뽑아줘.

[롱폼 전체]
{longform_text}

[규칙]
- 각 숏폼은 롱폼의 다른 포인트에서 추출 (겹치지 않게)
- 문장을 / 로 끊기 (자막 타이밍)
- 30초 분량 (80~100자)
- 각 숏폼마다 다른 훅 (첫 1~2초 임팩트)
- 의료법: 효과보장/전후비교 금지

JSON 배열로만 출력 (다른 텍스트 없이):
[
  {{"id": 1, "hook": "첫1-2초 임팩트 훅", "script": "내용 / 내용 / 내용 (80~100자)", "thumbnail_text": "썸네일 문구"}},
  {{"id": 2, "hook": "첫1-2초 임팩트 훅", "script": "내용 / 내용 / 내용 (80~100자)", "thumbnail_text": "썸네일 문구"}},
  {{"id": 3, "hook": "첫1-2초 임팩트 훅", "script": "내용 / 내용 / 내용 (80~100자)", "thumbnail_text": "썸네일 문구"}},
  {{"id": 4, "hook": "첫1-2초 임팩트 훅", "script": "내용 / 내용 / 내용 (80~100자)", "thumbnail_text": "썸네일 문구"}}
]"""

        resp3 = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=1500,
            messages=[{"role":"user","content":shorts_prompt}]
        )
        shorts_raw = resp3.content[0].text.strip().replace("```json","").replace("```","").strip()
        if "[" in shorts_raw:
            shorts_raw = shorts_raw[shorts_raw.find("["):shorts_raw.rfind("]")+1]
        try:
            shortforms = json.loads(shorts_raw)
        except Exception:
            shortforms = []

        result = {
            "keywords": meta.get("keywords", [category]),
            "titles": {
                "seo": meta.get("title_seo", ""),
                "curiosity": meta.get("title_curiosity", ""),
                "empathy": meta.get("title_empathy", "")
            },
            "thumbnails": [
                {"text": meta.get("thumbnail1",""), "concept": ""},
                {"text": meta.get("thumbnail2",""), "concept": ""},
                {"text": meta.get("thumbnail3",""), "concept": ""},
            ],
            "longform": longform_text,
            "shortforms": shortforms,
            "description": meta.get("description",""),
            "hashtags": meta.get("hashtags","").split(),
            "hooks": [meta.get("hook1",""), meta.get("hook2",""), meta.get("hook3","")],
            "multilang": {
                "en": meta.get("en", {}),
                "zh": meta.get("zh", {}),
                "ja": meta.get("ja", {})
            }
        }

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = CONTENT_AI_DIR / f"{ts}_youtube_{category}.json"
        out.write_text(json.dumps({
            "type":"youtube","category":category,"vtype":vtype,
            "angle":angle,"angle_desc":angle_desc,
            "created_at":datetime.now().isoformat(),"result":result
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        result["angle"] = angle
        result["angle_desc"] = angle_desc
        return jsonify({"success":True, "data":result})
    except Exception as e:
        return jsonify({"success":False, "error":str(e)})



@app.route("/api/content_ai/face", methods=["POST"])
def api_content_ai_face():
    """얼굴형 분석 릴스 스크립트 - Claude Vision 직접 호출"""
    try:
        import anthropic as _ant
        data = request.get_json() or {}
        image_b64 = data.get("image_base64","")
        media_type = data.get("media_type","image/jpeg")
        mode = data.get("mode","concern")
        person_name = data.get("person_name","")
        concern_area = data.get("concern_area","눈")

        if not image_b64:
            return jsonify({"success":False,"error":"이미지가 없어요"})

        prompt = f"""당신은 팝성형외과 인스타그램 릴스 전문 스크립트 작가입니다.

## [모드]
{"연예인 얼굴분석 모드" if mode=="celebrity" else "고민형 분석 모드"}
{"인물명: " + person_name if person_name else ""}
{"고민 부위: " + concern_area if mode=="concern" else ""}

## [의료법/초상권 준수 - 절대 규칙]
1. 시술/성형 여부 추측/단정 절대 금지
2. 전후 비교/효과 보장 금지
3. 부정적 외모 평가/비하 금지 - 전 구간 호의적 톤
4. 최상급/보장 표현 금지
5. 시술 유도/병원 홍보 금지
6. 거짓/과장 금지

## [구조]
{"후킹(0:00~0:03) -> 인사(0:03~0:06) -> 눈/코/입/얼굴전체 분석(0:06~0:50) -> 내면 칭찬 마무리(0:50~1:00)" if mode=="celebrity" else "후킹(0:00~0:03) -> 인사+고민도입(0:03~0:10) -> 눈/코/입/리프팅 분석(0:10~0:50) -> 댓글유도(0:50~1:00)"}
인사 고정: "안녕하세요, 팝성형외과 000 원장입니다."
{"마무리: 인물의 내면 태도/마인드 칭찬" if mode=="celebrity" else "마무리: 혹시 고민이 있으신 분들은 댓글 남겨주세요."}
마지막 줄: *본 콘텐츠는 AI 기반 도구의 도움을 받아 제작된 미적 분석 콘텐츠이며, 특정인의 시술 여부와 무관하고 진단/치료를 대체하지 않습니다.

## [출력 - JSON으로만]
{{
  "mode": "{mode}",
  "face_type": "얼굴형",
  "face_features": "주요 특징",
  "strength": "장점",
  "hook": "첫 1-2초 후킹 (12자 내외)",
  "titles": {{"a":"SEO형","b":"궁금증형","c":"감탄형"}},
  "thumbnails": [{{"text":"문구1","concept":"컨셉1"}},{{"text":"문구2","concept":"컨셉2"}},{{"text":"문구3","concept":"컨셉3"}}],
  "reels_script": {{"0-3초":"후킹","3-10초":"인사+도입","10-50초":"부위별 분석","50-60초":"마무리+고지"}},
  "caption": "캡션 2-3줄",
  "hashtags": ["#얼굴분석","#황금비율","#이목구비","#안면비율","#성형외과","#팝성형외과","#강남성형외과","#릴스","#뷰티","#얼굴황금비율"],
  "hooks": ["자막1","자막2","자막3"]
}}
"""

        client = _ant.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY",""))
        resp = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=2000,
            messages=[{"role":"user","content":[
                {"type":"image","source":{"type":"base64","media_type":media_type,"data":image_b64}},
                {"type":"text","text":prompt}
            ]}]
        )
        raw = resp.content[0].text.strip()
        raw = raw.replace("```json","").replace("```","").strip()
        if raw.find('{') >= 0:
            raw = raw[raw.find('{'):raw.rfind('}')+1]
        try:
            result = json.loads(raw)
        except Exception:
            result = {"mode": mode, "face_type": "분석 완료", "face_features": raw[:200], "strength": "", "hook": "", "titles": {"a":"","b":"","c":""}, "thumbnails": [], "reels_script": {"0-3초": raw[:100]}, "caption": "", "hashtags": [], "hooks": []}

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = CONTENT_AI_DIR / f"{ts}_face_{mode}.json"
        out.write_text(json.dumps({
            "type":"face","mode":mode,"created_at":datetime.now().isoformat(),"result":result
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        return jsonify({"success":True,"data":result})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})


@app.route("/api/content_ai/keyword_reels", methods=["POST"])
def api_content_ai_keyword_reels():
    """키워드 -> 릴스 주제 추천 - Claude API 직접 호출"""
    try:
        import anthropic as _ant
        data = request.get_json() or {}
        keyword = data.get("keyword","")
        category = data.get("category","전체")

        if not keyword:
            return jsonify({"success":False,"error":"키워드를 입력해주세요"})

        # YouTube + 네이버 키워드 수집
        yt_results = []
        naver_results = []

        yt_key = os.environ.get("YOUTUBE_API_KEY","")
        if yt_key:
            try:
                import urllib.request as _ur, urllib.parse as _up
                params = _up.urlencode({"part":"snippet","q":keyword,"type":"video","order":"viewCount","regionCode":"KR","maxResults":"5","key":yt_key})
                req = _ur.urlopen(f"https://www.googleapis.com/youtube/v3/search?{params}", timeout=5)
                items = json.loads(req.read().decode())["items"]
                yt_results = [i["snippet"]["title"] for i in items[:5]]
            except Exception:
                pass

        naver_id = os.environ.get("NAVER_CLIENT_ID","")
        naver_secret = os.environ.get("NAVER_CLIENT_SECRET","")
        if naver_id and naver_secret:
            try:
                import urllib.request as _ur, urllib.parse as _up, re as _re
                q = _up.quote(keyword)
                req = _ur.Request(f"https://openapi.naver.com/v1/search/blog?query={q}&display=5&sort=date")
                req.add_header("X-Naver-Client-Id", naver_id)
                req.add_header("X-Naver-Client-Secret", naver_secret)
                res = _ur.urlopen(req, timeout=5)
                items = json.loads(res.read().decode())["items"]
                naver_results = [_re.sub("<[^>]*>","",i["title"]) for i in items[:5]]
            except Exception:
                pass

        prompt = f"""당신은 팝성형외과 릴스 기획 전문가입니다.

[입력 키워드] {keyword}
[카테고리] {category}
[YouTube 트렌딩] {', '.join(yt_results) if yt_results else '데이터 없음'}
[네이버 실검] {', '.join(naver_results) if naver_results else '데이터 없음'}

위 데이터를 기반으로 팝성형외과 인스타그램 릴스 주제 5개를 추천해주세요.

의료법 준수:
- 시술 효과 보장 금지
- 최상급 표현 금지
- 부정적 외모 표현 금지

JSON으로만 응답:
{{
  "keyword": "입력키워드",
  "recommendations": [
    {{
      "id": 1,
      "title": "릴스 제목",
      "hook": "첫 1초 훅 (12자 이내)",
      "points": ["핵심 포인트1", "핵심 포인트2", "핵심 포인트3"],
      "script_30sec": "30초 대본",
      "hashtags": ["#태그1", "#태그2", "#태그3", "#태그4", "#태그5"],
      "expected_performance": "예상 성과"
    }}
  ]
}}
"""

        client = _ant.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY",""))
        resp = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=3000,
            messages=[{"role":"user","content":prompt}]
        )
        raw = resp.content[0].text.strip()
        raw = raw.replace("```json","").replace("```","").strip()
        if raw.find('{') >= 0:
            raw = raw[raw.find('{'):raw.rfind('}')+1]
        try:
            result = json.loads(raw)
        except Exception:
            result = {"keyword": keyword, "recommendations": [{"id":1,"title":raw[:100],"hook":"","points":[],"script_30sec":raw[:300],"hashtags":[],"expected_performance":""}]}

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = CONTENT_AI_DIR / f"{ts}_keyword_{keyword[:20]}.json"
        out.write_text(json.dumps({
            "type":"keyword_reels","keyword":keyword,"category":category,
            "created_at":datetime.now().isoformat(),"result":result
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        return jsonify({"success":True,"data":result})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})


@app.route("/api/content_ai/list")
def api_content_ai_list():
    # 생성된 콘텐츠 AI 결과 목록
    try:
        files = sorted(CONTENT_AI_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        items = []
        for f in files[:50]:
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                items.append({
                    "filename": f.name,
                    "type": d.get("type",""),
                    "category": d.get("category",""),
                    "keyword": d.get("keyword",""),
                    "mode": d.get("mode",""),
                    "created_at": d.get("created_at","")[:16],
                })
            except Exception:
                continue
        return jsonify(items)
    except Exception as e:
        return jsonify({"error":str(e)})


# -- 콘텐츠 AI 페이지 HTML ------------------------------------------
CONTENT_AI_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>콘텐츠 AI - 팝성형외과</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI','Noto Sans KR',sans-serif;background:#FAFAF8;color:#1A1A1A}
.nav{background:#1a1a2e;display:flex;padding:0 24px;position:sticky;top:0;z-index:100}
.nav a{padding:13px 20px;font-size:13px;color:#a0a0c0;text-decoration:none;border-bottom:3px solid transparent}
.nav a:hover{color:#C9956C}.nav a.on{color:#C9956C;border-bottom-color:#C9956C}
.header{background:linear-gradient(135deg,#C9956C,#E8927C);color:#fff;padding:24px 40px}
.header h1{font-size:22px;font-weight:700}
.header p{font-size:13px;opacity:.85;margin-top:4px}
.wrap{max-width:1200px;margin:0 auto;padding:28px 24px}
.tabs{display:flex;gap:4px;background:#fff;border-radius:10px;padding:4px;box-shadow:0 2px 8px rgba(0,0,0,.06);margin-bottom:24px;width:fit-content}
.tab{padding:8px 20px;border-radius:7px;font-size:13px;font-weight:500;cursor:pointer;border:none;background:transparent;color:#6b7280}
.tab.on{background:#C9956C;color:#fff}
.panel{display:none}.panel.on{display:block}
.grid{display:grid;grid-template-columns:320px 1fr;gap:20px}
.card{background:#fff;border-radius:14px;padding:24px;box-shadow:0 2px 10px rgba(0,0,0,.06)}
.card h3{font-size:15px;font-weight:700;margin-bottom:16px;color:#1A1A1A}
.form-group{margin-bottom:14px}
label{font-size:12px;font-weight:600;color:#6b7280;display:block;margin-bottom:6px}
select,input[type=text]{width:100%;padding:9px 12px;border:1px solid #e5e7eb;border-radius:8px;font-size:14px;color:#1A1A1A}
.radio-group{display:flex;flex-direction:column;gap:8px}
.radio-item{display:flex;align-items:center;gap:10px;padding:10px 14px;border:1px solid #e5e7eb;border-radius:8px;cursor:pointer;transition:all .2s}
.radio-item.on{border-color:#C9956C;background:#fff8f5}
.radio-item input{accent-color:#C9956C}
.btn{width:100%;padding:12px;border:none;border-radius:10px;font-size:14px;font-weight:700;cursor:pointer;transition:all .2s;margin-top:8px}
.btn-main{background:linear-gradient(135deg,#C9956C,#E8927C);color:#fff}
.btn-main:hover{opacity:.9}
.btn-main:disabled{background:#d1d5db;cursor:not-allowed}
.result-area{min-height:400px}
.result-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;height:300px;color:#9ca3af;font-size:14px;gap:8px}
.keyword-badges{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px}
.badge{padding:4px 12px;border-radius:20px;font-size:12px;font-weight:600;background:#fff8f5;color:#C9956C;border:1px solid #f4d4c0}
.title-tabs{display:flex;gap:4px;margin-bottom:8px}
.ttab{padding:5px 12px;border-radius:6px;font-size:12px;cursor:pointer;border:1px solid #e5e7eb;background:#fff;color:#6b7280}
.ttab.on{background:#C9956C;color:#fff;border-color:#C9956C}
.script-box{background:#f9fafb;border-radius:10px;padding:16px;font-size:13px;line-height:1.8;white-space:pre-wrap;max-height:400px;overflow-y:auto;margin-bottom:12px}
.copy-btn{padding:6px 14px;background:#1a1a2e;color:#fff;border:none;border-radius:6px;font-size:12px;cursor:pointer}
.copy-btn:hover{background:#2d2d4e}
.shortform-cards{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:16px}
.sf-card{background:#f9fafb;border-radius:10px;padding:12px;font-size:12px;line-height:1.7}
.sf-title{font-weight:700;font-size:11px;color:#C9956C;margin-bottom:6px}
.hashtags{display:flex;flex-wrap:wrap;gap:4px}
.htag{padding:3px 10px;background:#f0f9ff;color:#0ea5e9;border-radius:20px;font-size:11px;cursor:pointer}
.htag:hover{background:#bae6fd}
.upload-area{border:2px dashed #e5e7eb;border-radius:12px;padding:40px;text-align:center;cursor:pointer;transition:all .2s;margin-bottom:14px}
.upload-area:hover{border-color:#C9956C;background:#fff8f5}
.upload-area img{max-width:200px;max-height:200px;border-radius:8px;object-fit:cover}
.face-result{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px}
.face-card{background:#f9fafb;border-radius:10px;padding:14px}
.face-card h4{font-size:12px;font-weight:700;color:#C9956C;margin-bottom:6px}
.timeline{display:flex;flex-direction:column;gap:8px}
.tl-item{display:flex;gap:10px;align-items:flex-start}
.tl-time{font-size:11px;font-weight:700;color:#C9956C;min-width:60px;padding-top:2px}
.tl-text{font-size:13px;line-height:1.6;color:#374151}
.rec-cards{display:flex;flex-direction:column;gap:12px}
.rec-card{background:#fff;border-radius:12px;padding:16px;box-shadow:0 2px 8px rgba(0,0,0,.06)}
.rec-num{display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;background:#C9956C;color:#fff;border-radius:50%;font-size:12px;font-weight:700;margin-right:8px}
.rec-title{font-size:14px;font-weight:700;color:#1A1A1A;margin-bottom:8px}
.rec-hook{font-size:13px;color:#C9956C;font-weight:600;margin-bottom:8px;padding:6px 10px;background:#fff8f5;border-radius:6px}
.rec-points{font-size:13px;color:#374151;margin-bottom:10px;line-height:1.8}
.script-toggle{font-size:12px;color:#6b7280;cursor:pointer;margin-bottom:6px}
.script-toggle:hover{color:#C9956C}
.rec-script{display:none;background:#f9fafb;border-radius:8px;padding:12px;font-size:12px;line-height:1.8;white-space:pre-wrap}
.loading{display:flex;align-items:center;justify-content:center;gap:10px;padding:60px;color:#9ca3af;font-size:14px}
/* 단계 체크 */
.stage-bar{display:flex;gap:4px;margin-top:12px;flex-wrap:wrap}
.stage-btn{padding:4px 10px;border-radius:20px;font-size:11px;font-weight:600;border:1px solid #e5e7eb;background:#fff;color:#6b7280;cursor:pointer;transition:all .2s}
.stage-btn.done{background:#1a1a2e;color:#fff;border-color:#1a1a2e}
.stage-btn.current{background:#C9956C;color:#fff;border-color:#C9956C}
.spinner{width:24px;height:24px;border:3px solid #f3f4f6;border-top-color:#C9956C;border-radius:50%;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
</style>
</head>
<body>
<div class="nav">
  <a href="/">홈</a>
  <a href="/blog">블로그</a>
  <a href="/youtube">유튜브</a>
  <a href="/magazine">매거진</a>
  <a href="/sov">노출 점유율</a>
  <a href="/content_ai" class="on">콘텐츠 AI</a>
</div>
<div class="header">
  <h1>POP 콘텐츠 AI</h1>
  <p>유튜브 스크립트 / 얼굴형 분석 릴스 / 키워드 릴스 주제 추천</p>
</div>
<div class="wrap">
  <div class="tabs">
    <button class="tab on" onclick="switchTab('youtube',this)">🎬 유튜브 스크립트</button>
    <button class="tab" onclick="switchTab('shorts',this)">⚡ 숏츠 10개 생성</button>
    <button class="tab" onclick="switchTab('face',this)">👤 얼굴형 분석</button>
    <button class="tab" onclick="switchTab('keyword',this)">🔑 키워드 릴스</button>
    <button class="tab" onclick="switchTab('history',this);loadHistory()">📋 히스토리</button>
  </div>

  <!-- 유튜브 스크립트 -->
  <div class="panel on" id="panel-youtube">
    <div class="grid">
      <div class="card">
        <h3>설정</h3>
        <div class="form-group">
          <label>카테고리</label>
          <select id="yt-category">
            <option>눈성형</option>
            <option>코성형</option>
            <option>리프팅</option>
          </select>
        </div>
        <div class="form-group">
          <label>영상 유형</label>
          <div class="radio-group">
            <label class="radio-item on" onclick="selectRadio(this,'yt-type-group')">
              <input type="radio" name="yt-type" value="롱폼 3분" checked> 
              <div><div style="font-weight:600;font-size:13px">롱폼 3분</div><div style="font-size:11px;color:#9ca3af">YouTube 메인 콘텐츠</div></div>
            </label>
            <label class="radio-item" onclick="selectRadio(this,'yt-type-group')">
              <input type="radio" name="yt-type" value="숏폼 30초">
              <div><div style="font-weight:600;font-size:13px">숏폼 30초</div><div style="font-size:11px;color:#9ca3af">Shorts / Reels</div></div>
            </label>
          </div>
        </div>
        <button class="btn btn-main" id="yt-btn" onclick="generateYoutube()">🎬 스크립트 생성</button>
      </div>
      <div class="card" style="overflow-y:auto;max-height:85vh">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
          <div style="font-size:14px;font-weight:700;color:#1A1A1A">생성된 스크립트 <span id="yt-count" style="color:#C9956C"></span></div>
          <button onclick="document.getElementById('yt-list').innerHTML='';document.getElementById('yt-count').textContent=''" style="padding:4px 10px;border:1px solid #e5e7eb;border-radius:6px;font-size:11px;cursor:pointer;background:#fff">전체 삭제</button>
        </div>
        <div id="yt-list">
          <div class="result-empty" style="padding:40px">
            <div style="font-size:32px">🎬</div>
            <div>좌측 설정 후 "스크립트 생성" 클릭</div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- 얼굴형 분석 -->
  <div class="panel" id="panel-face">
    <div class="grid">
      <div class="card">
        <h3>설정</h3>
        <div class="form-group">
          <label>분석 모드</label>
          <div class="radio-group">
            <label class="radio-item" onclick="selectFaceMode('celebrity',this)">
              <input type="radio" name="face-mode" value="celebrity">
              <div><div style="font-weight:600;font-size:13px">연예인 얼굴분석</div><div style="font-size:11px;color:#9ca3af">얼굴 미학 분석 콘텐츠</div></div>
            </label>
            <label class="radio-item on" onclick="selectFaceMode('concern',this)">
              <input type="radio" name="face-mode" value="concern" checked>
              <div><div style="font-weight:600;font-size:13px">고민형 분석</div><div style="font-size:11px;color:#9ca3af">고민 해결 교육 콘텐츠</div></div>
            </label>
          </div>
        </div>
        <div id="celebrity-input" style="display:none" class="form-group">
          <label>인물명 (선택)</label>
          <input type="text" id="person-name" placeholder="예: 장원영">
        </div>
        <div id="concern-input" class="form-group">
          <label>고민 부위</label>
          <select id="concern-area">
            <option>눈</option><option>코</option><option>리프팅</option><option>전체</option>
          </select>
        </div>
        <div class="form-group">
          <label>이미지 업로드</label>
          <div class="upload-area" id="upload-area" onclick="document.getElementById('face-img').click()">
            <input type="file" id="face-img" accept="image/*" style="display:none" onchange="previewImage(this)">
            <div id="upload-placeholder">
              <div style="font-size:32px;margin-bottom:8px">📷</div>
              <div style="font-size:13px;color:#9ca3af">클릭하여 이미지 업로드</div>
            </div>
          </div>
        </div>
        <button class="btn btn-main" id="face-btn" onclick="generateFace()">👤 분석 시작</button>
      </div>
      <div class="card" style="overflow-y:auto;max-height:85vh">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
          <div style="font-size:14px;font-weight:700;color:#1A1A1A">분석 결과 <span id="face-count" style="color:#C9956C"></span></div>
          <button onclick="document.getElementById('face-list').innerHTML='';document.getElementById('face-count').textContent=''" style="padding:4px 10px;border:1px solid #e5e7eb;border-radius:6px;font-size:11px;cursor:pointer;background:#fff">전체 삭제</button>
        </div>
        <div id="face-list">
          <div class="result-empty" style="padding:40px">
            <div style="font-size:32px">👤</div>
            <div>이미지 업로드 후 "분석 시작" 클릭</div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- 숏츠 10개 배치 생성 -->
  <div class="panel" id="panel-shorts">
    <div class="grid">
      <div class="card">
        <h3>설정</h3>
        <div class="form-group">
          <label>생성 개수</label>
          <select id="shorts-count">
            <option value="10">10개</option>
            <option value="5">5개</option>
            <option value="20">20개</option>
          </select>
        </div>
        <div style="background:#fff8f5;border-radius:10px;padding:12px;margin-bottom:14px;font-size:12px;color:#6b7280;line-height:1.7">
          <div style="font-weight:700;color:#C9956C;margin-bottom:4px">✨ 스마트 중복 방지</div>
          기존에 생성된 주제를 자동으로 파악해서 겹치지 않는 새로운 주제로 생성해요.
        </div>
        <button class="btn btn-main" id="shorts-btn" onclick="generateShorts()">⚡ 숏츠 생성</button>
      </div>
      <div class="card" style="overflow-y:auto;max-height:85vh">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
          <div style="font-size:14px;font-weight:700;color:#1A1A1A">생성된 숏츠 <span id="shorts-count" style="color:#C9956C"></span></div>
          <button onclick="document.getElementById('shorts-list').innerHTML='';document.getElementById('shorts-count').textContent=''" style="padding:4px 10px;border:1px solid #e5e7eb;border-radius:6px;font-size:11px;cursor:pointer;background:#fff">전체 삭제</button>
        </div>
        <div id="shorts-list">
          <div class="result-empty" style="padding:40px">
            <div style="font-size:32px">⚡</div>
            <div>버튼 클릭 시 중복 없이 숏츠 생성</div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- 히스토리 -->
  <div class="panel" id="panel-history">
    <div class="card">
      <h3>📋 생성 히스토리</h3>
      <div id="history-list" style="margin-top:16px">
        <div class="loading">히스토리 로딩 중...</div>
      </div>
    </div>
  </div>

  <!-- 키워드 릴스 -->
  <div class="panel" id="panel-keyword">
    <div class="grid">
      <div class="card">
        <h3>설정</h3>
        <div class="form-group">
          <label>키워드 입력</label>
          <input type="text" id="kw-input" placeholder="예: 쌍꺼풀 재수술">
        </div>
        <div class="form-group">
          <label>카테고리</label>
          <select id="kw-category">
            <option>전체</option>
            <option>눈성형</option>
            <option>코성형</option>
            <option>리프팅</option>
          </select>
        </div>
        <button class="btn btn-main" id="kw-btn" onclick="generateKeyword()">🔑 주제 추천받기</button>
      </div>
      <div class="card" style="overflow-y:auto;max-height:85vh">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
          <div style="font-size:14px;font-weight:700;color:#1A1A1A">추천 결과 <span id="kw-count" style="color:#C9956C"></span></div>
          <button onclick="document.getElementById('kw-list').innerHTML='';document.getElementById('kw-count').textContent=''" style="padding:4px 10px;border:1px solid #e5e7eb;border-radius:6px;font-size:11px;cursor:pointer;background:#fff">전체 삭제</button>
        </div>
        <div id="kw-list">
          <div class="result-empty" style="padding:40px">
            <div style="font-size:32px">🔑</div>
            <div>키워드 입력 후 "주제 추천받기" 클릭</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>

<script>
let faceMode = 'concern';
let faceImageB64 = '';
let faceMediaType = 'image/jpeg';

function switchTab(id, btn) {
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('on'));
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('on'));
  btn.classList.add('on');
  document.getElementById('panel-'+id).classList.add('on');
}

function selectRadio(el, group) {
  el.closest('.radio-group').querySelectorAll('.radio-item').forEach(i=>i.classList.remove('on'));
  el.classList.add('on');
}

function selectFaceMode(mode, el) {
  faceMode = mode;
  el.closest('.radio-group').querySelectorAll('.radio-item').forEach(i=>i.classList.remove('on'));
  el.classList.add('on');
  document.getElementById('celebrity-input').style.display = mode==='celebrity'?'block':'none';
  document.getElementById('concern-input').style.display = mode==='concern'?'block':'none';
}

function previewImage(input) {
  const file = input.files[0];
  if (!file) return;
  faceMediaType = file.type || 'image/jpeg';
  const reader = new FileReader();
  reader.onload = e => {
    faceImageB64 = e.target.result.split(',')[1];
    document.getElementById('upload-placeholder').innerHTML = 
      `<img src="${e.target.result}" style="max-width:200px;max-height:200px;border-radius:8px">`;
  };
  reader.readAsDataURL(file);
}

function copyText(text) {
  navigator.clipboard.writeText(text);
}

async function generateYoutube() {
  const btn = document.getElementById('yt-btn');
  const list = document.getElementById('yt-list');
  btn.disabled = true; btn.textContent = '⏳ 생성 중...';

  // 로딩 카드 맨 위에 추가
  const loadingId = 'loading-' + Date.now();
  const loadingCard = document.createElement('div');
  loadingCard.id = loadingId;
  loadingCard.className = 'loading';
  loadingCard.style.cssText = 'border:1px solid #f3f4f6;border-radius:12px;padding:20px;margin-bottom:12px';
  loadingCard.innerHTML = '<div class="spinner"></div>스크립트 생성 중... (30초~1분 소요)';
  list.insertBefore(loadingCard, list.firstChild);
  // 빈 상태 메시지 제거
  list.querySelectorAll('.result-empty').forEach(e=>e.remove());

  const category = document.getElementById('yt-category').value;
  const type = document.querySelector('input[name="yt-type"]:checked').value;
  const now = new Date().toLocaleTimeString('ko-KR', {hour:'2-digit',minute:'2-digit'});

  try {
    const r = await fetch('/api/content_ai/youtube', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({category, type})
    });
    const d = await r.json();
    if (!d.success) throw new Error(d.error);
    const data = d.data;
    const uid = Date.now();

    // 새 결과 카드 생성
    const card = document.createElement('div');
    card.style.cssText = 'border:1px solid #f3f4f6;border-radius:12px;padding:20px;margin-bottom:16px;background:#fff;box-shadow:0 2px 8px rgba(0,0,0,.04)';
    card.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px">
        <div>
          <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:6px">
            <span class="badge" style="font-size:12px">${category}</span>
            <span class="badge" style="background:#f0f4ff;color:#4f46e5;font-size:12px">${type}</span>
            ${data.angle ? `<span class="badge" style="background:#fff0f9;color:#c026d3;font-size:12px">📐 ${data.angle}</span>` : ''}
            <span style="font-size:11px;color:#9ca3af">${now}</span>
          </div>
          <div class="keyword-badges">
            ${(data.keywords||[]).map(k=>`<span class="badge">${k}</span>`).join('')}
          </div>
        </div>
        <button onclick="this.closest('div[style]').remove();updateCount('yt')" style="font-size:13px;color:#9ca3af;border:none;background:none;cursor:pointer;flex-shrink:0">✕</button>
      </div>

      <div style="margin-bottom:14px;padding:12px;background:#fafafa;border-radius:8px">
        <div style="font-size:11px;font-weight:700;color:#C9956C;margin-bottom:8px;letter-spacing:.05em">제목 추천</div>
        <div style="display:flex;flex-direction:column;gap:6px">
          <div>
            <span style="font-size:10px;background:#e8f0fe;color:#4f8ef7;padding:2px 6px;border-radius:4px;margin-right:6px">SEO</span>
            <span style="font-size:13px;font-weight:600;color:#1A1A1A">${data.titles?.seo||''}</span>
            <button class="copy-btn" style="margin-left:8px;padding:2px 8px;font-size:10px" onclick="copyText('${(data.titles?.seo||'').replace(/'/g,"\\\\'")}')">복사</button>
          </div>
          <div>
            <span style="font-size:10px;background:#fff0e8;color:#f7934f;padding:2px 6px;border-radius:4px;margin-right:6px">궁금증</span>
            <span style="font-size:12px;color:#374151">${data.titles?.curiosity||''}</span>
          </div>
          <div>
            <span style="font-size:10px;background:#e8faf3;color:#4fd19e;padding:2px 6px;border-radius:4px;margin-right:6px">공감</span>
            <span style="font-size:12px;color:#374151">${data.titles?.empathy||''}</span>
          </div>
        </div>
      </div>

      <div style="margin-bottom:14px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <div style="font-size:11px;font-weight:700;color:#C9956C;letter-spacing:.05em">롱폼 대본</div>
          <button class="copy-btn" onclick="copyText(document.getElementById('lf-${uid}').innerText)">전체 복사</button>
        </div>
        <div id="lf-${uid}" style="background:#f9fafb;border-radius:8px;padding:14px;font-size:13px;line-height:2;white-space:pre-wrap;max-height:300px;overflow-y:auto;color:#1A1A1A">${(data.longform||'').replace(/\\n/g,'\\n')}</div>
      </div>

      <div style="margin-bottom:14px">
        <div style="font-size:11px;font-weight:700;color:#C9956C;margin-bottom:8px;letter-spacing:.05em">숏폼 ${(data.shortforms||[]).length}개 추출</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
          ${(data.shortforms||[]).map((s,i)=>`
            <div style="background:#f9fafb;border-radius:8px;padding:12px">
              <div style="font-size:11px;font-weight:700;color:#C9956C;margin-bottom:4px">숏폼 ${i+1}</div>
              ${s.hook ? `<div style="font-size:12px;font-weight:600;color:#1A1A1A;margin-bottom:6px">${s.hook}</div>` : ''}
              <div id="sf-${uid}-${i}" style="font-size:12px;line-height:1.9;color:#374151;white-space:pre-wrap">${(s.script||s||'').split('/').join('\n/ ')}</div>
              <button class="copy-btn" style="margin-top:8px;font-size:10px" onclick="copyText(document.getElementById('sf-${uid}-${i}').innerText)">복사</button>
            </div>`).join('')}
        </div>
      </div>

      <div style="margin-bottom:14px">
        <div style="font-size:11px;font-weight:700;color:#C9956C;margin-bottom:6px;letter-spacing:.05em">해시태그</div>
        <div class="hashtags">
          ${(data.hashtags||[]).map(h=>`<span class="htag" style="font-size:11px" onclick="copyText('${h}')">${h}</span>`).join('')}
        </div>
      </div>

      ${(data.multilang && (data.multilang.en || data.multilang.zh || data.multilang.ja)) ? `
      <div style="margin-bottom:14px">
        <div style="font-size:11px;font-weight:700;color:#C9956C;margin-bottom:10px;letter-spacing:.05em">🌐 다국어 버전</div>
        <div style="display:flex;flex-direction:column;gap:8px">

          ${data.multilang.en ? `
          <div style="background:#f0f4ff;border-radius:8px;padding:12px">
            <div style="font-size:11px;font-weight:700;color:#4f46e5;margin-bottom:6px">🇺🇸 English</div>
            <div style="font-size:13px;font-weight:600;color:#1A1A1A;margin-bottom:4px">${data.multilang.en.title||''}</div>
            <div style="font-size:12px;color:#6b7280;margin-bottom:6px">${data.multilang.en.thumbnail||''}</div>
            <div style="display:flex;flex-wrap:wrap;gap:4px">
              ${(data.multilang.en.hashtags||'').split(' ').filter(h=>h).map(h=>`<span class="htag" style="font-size:10px;background:#e0e7ff;color:#4f46e5" onclick="copyText('${h}')">${h}</span>`).join('')}
            </div>
          </div>` : ''}

          ${data.multilang.zh ? `
          <div style="background:#fff7f0;border-radius:8px;padding:12px">
            <div style="font-size:11px;font-weight:700;color:#ea580c;margin-bottom:6px">🇨🇳 中文</div>
            <div style="font-size:13px;font-weight:600;color:#1A1A1A;margin-bottom:4px">${data.multilang.zh.title||''}</div>
            <div style="font-size:12px;color:#6b7280;margin-bottom:6px">${data.multilang.zh.thumbnail||''}</div>
            <div style="display:flex;flex-wrap:wrap;gap:4px">
              ${(data.multilang.zh.hashtags||'').split(' ').filter(h=>h).map(h=>`<span class="htag" style="font-size:10px;background:#ffedd5;color:#ea580c" onclick="copyText('${h}')">${h}</span>`).join('')}
            </div>
          </div>` : ''}

          ${data.multilang.ja ? `
          <div style="background:#f0fdf4;border-radius:8px;padding:12px">
            <div style="font-size:11px;font-weight:700;color:#16a34a;margin-bottom:6px">🇯🇵 日本語</div>
            <div style="font-size:13px;font-weight:600;color:#1A1A1A;margin-bottom:4px">${data.multilang.ja.title||''}</div>
            <div style="font-size:12px;color:#6b7280;margin-bottom:6px">${data.multilang.ja.thumbnail||''}</div>
            <div style="display:flex;flex-wrap:wrap;gap:4px">
              ${(data.multilang.ja.hashtags||'').split(' ').filter(h=>h).map(h=>`<span class="htag" style="font-size:10px;background:#dcfce7;color:#16a34a" onclick="copyText('${h}')">${h}</span>`).join('')}
            </div>
          </div>` : ''}

        </div>
      </div>` : ''}

      ${makeStageBar(uid)}
    `;

    // 로딩 카드 교체
    list.replaceChild(card, document.getElementById(loadingId));
    updateCount('yt');

  } catch(e) {
    const errCard = document.createElement('div');
    errCard.style.cssText = 'border:1px solid #fee2e2;border-radius:12px;padding:16px;margin-bottom:12px;color:#ef4444;font-size:13px';
    errCard.innerHTML = `오류: ${e.message} <button onclick="this.parentElement.remove()" style="margin-left:8px;border:none;background:none;cursor:pointer;color:#9ca3af">✕</button>`;
    list.replaceChild(errCard, document.getElementById(loadingId));
  } finally {
    btn.disabled=false; btn.textContent='🎬 스크립트 생성';
  }
}

// 단계 목록
const STAGES = ['생성완료', '촬영완료', '편집완료', '업로드예정', '업로드완료'];

function makeStageBar(id) {
  const saved = JSON.parse(localStorage.getItem('stage_'+id) || '{}');
  const currentIdx = saved.stage !== undefined ? saved.stage : 0;
  return `<div class="stage-bar" id="stagebar-${id}">
    ${STAGES.map((s,i) => `<button
      class="stage-btn ${i < currentIdx ? 'done' : i === currentIdx ? 'current' : ''}"
      onclick="setStage('${id}', ${i})"
    >${i < currentIdx ? '✓ ' : ''}${s}</button>`).join('')}
  </div>`;
}

function setStage(id, idx) {
  localStorage.setItem('stage_'+id, JSON.stringify({stage: idx, updated: new Date().toISOString()}));
  const bar = document.getElementById('stagebar-'+id);
  if (!bar) return;
  bar.querySelectorAll('.stage-btn').forEach((btn, i) => {
    btn.className = 'stage-btn ' + (i < idx ? 'done' : i === idx ? 'current' : '');
    btn.textContent = (i < idx ? '✓ ' : '') + STAGES[i];
  });
}

function updateCount(type) {
  const map = {yt:'yt-list', face:'face-list', kw:'kw-list', shorts:'shorts-list'};
  const countMap = {yt:'yt-count', face:'face-count', kw:'kw-count', shorts:'shorts-count'};
  const list = document.getElementById(map[type]);
  const countEl = document.getElementById(countMap[type]);
  if (!list || !countEl) return;
  const cnt = list.querySelectorAll('div[style*="border"]').length;
  countEl.textContent = cnt > 0 ? `(${cnt}개)` : '';
}

function showTitle(type, btn) {
  document.querySelectorAll('.ttab').forEach(t=>t.classList.remove('on'));
  btn.classList.add('on');
  ['seo','curiosity','empathy'].forEach(t=>{
    document.getElementById('title-'+t).style.display = t===type?'block':'none';
  });
}

async function generateFace() {
  if (!faceImageB64) { alert('이미지를 먼저 업로드해주세요!'); return; }
  const btn = document.getElementById('face-btn');
  const list = document.getElementById('face-list');
  btn.disabled=true; btn.textContent='⏳ 분석 중...';

  const loadingId = 'loading-' + Date.now();
  const loadingCard = document.createElement('div');
  loadingCard.id = loadingId;
  loadingCard.className = 'loading';
  loadingCard.style.cssText = 'border:1px solid #f3f4f6;border-radius:12px;padding:20px;margin-bottom:12px';
  loadingCard.innerHTML = '<div class="spinner"></div>얼굴 분석 중... (30초~1분 소요)';
  list.insertBefore(loadingCard, list.firstChild);
  list.querySelectorAll('.result-empty').forEach(e=>e.remove());

  const now = new Date().toLocaleTimeString('ko-KR', {hour:'2-digit',minute:'2-digit'});
  const uid = Date.now();

  try {
    const r = await fetch('/api/content_ai/face', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        image_base64: faceImageB64,
        media_type: faceMediaType,
        mode: faceMode,
        person_name: document.getElementById('person-name').value,
        concern_area: document.getElementById('concern-area').value
      })
    });
    const d = await r.json();
    if (!d.success) throw new Error(d.error);
    const data = d.data;
    const rs = data.reels_script || {};

    const card = document.createElement('div');
    card.style.cssText = 'border:1px solid #f3f4f6;border-radius:12px;padding:20px;margin-bottom:16px;background:#fff;box-shadow:0 2px 8px rgba(0,0,0,.04)';
    card.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px">
        <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
          <span class="badge" style="font-size:12px">${data.face_type||'분석완료'}</span>
          <span style="font-size:11px;color:#9ca3af">${faceMode==='celebrity'?'연예인':'고민형'} · ${now}</span>
        </div>
        <button onclick="this.closest('div[style]').remove();updateCount('face')" style="font-size:13px;color:#9ca3af;border:none;background:none;cursor:pointer">✕</button>
      </div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px">
        <div style="background:#fafafa;border-radius:8px;padding:12px">
          <div style="font-size:11px;font-weight:700;color:#C9956C;margin-bottom:6px">얼굴형 분석</div>
          <div style="font-size:14px;font-weight:700;color:#1A1A1A;margin-bottom:4px">${data.face_type||''}</div>
          <div style="font-size:12px;color:#6b7280;line-height:1.6">${data.face_features||''}</div>
        </div>
        <div style="background:#fafafa;border-radius:8px;padding:12px">
          <div style="font-size:11px;font-weight:700;color:#C9956C;margin-bottom:6px">장점</div>
          <div style="font-size:12px;color:#374151;line-height:1.6">${data.strength||''}</div>
        </div>
      </div>

      <div style="margin-bottom:14px;background:#fafafa;border-radius:8px;padding:14px">
        <div style="font-size:11px;font-weight:700;color:#C9956C;margin-bottom:10px;letter-spacing:.05em">30초 릴스 대본</div>
        <div style="display:flex;flex-direction:column;gap:8px">
          ${Object.entries(rs).map(([t,c])=>`
            <div style="display:flex;gap:12px;align-items:flex-start">
              <div style="color:#C9956C;font-weight:700;font-size:12px;min-width:55px;padding-top:2px">${t}</div>
              <div style="font-size:13px;color:#374151;line-height:1.8;flex:1">${c}</div>
            </div>`).join('')}
        </div>
      </div>

      <div style="margin-bottom:14px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <div style="font-size:11px;font-weight:700;color:#C9956C;letter-spacing:.05em">인스타 캡션</div>
          <button class="copy-btn" onclick="copyText(document.getElementById('cap-${uid}').innerText)">복사</button>
        </div>
        <div id="cap-${uid}" style="background:#f9fafb;border-radius:8px;padding:12px;font-size:12px;line-height:1.9;white-space:pre-wrap;color:#374151">${data.caption||''}</div>
      </div>

      <div style="margin-bottom:12px">
        <div class="hashtags">
          ${(data.hashtags||[]).map(h=>`<span class="htag" style="font-size:11px" onclick="copyText('${h}')">${h}</span>`).join('')}
        </div>
      </div>

      ${makeStageBar(uid)}
    `;

    list.replaceChild(card, document.getElementById(loadingId));
    updateCount('face');

  } catch(e) {
    const errCard = document.createElement('div');
    errCard.style.cssText = 'border:1px solid #fee2e2;border-radius:12px;padding:16px;margin-bottom:12px;color:#ef4444;font-size:13px';
    errCard.innerHTML = `오류: ${e.message} <button onclick="this.parentElement.remove()" style="margin-left:8px;border:none;background:none;cursor:pointer;color:#9ca3af">✕</button>`;
    list.replaceChild(errCard, document.getElementById(loadingId));
  } finally {
    btn.disabled=false; btn.textContent='👤 분석 시작';
  }
}

async function generateKeyword() {
  const kw = document.getElementById('kw-input').value.trim();
  if (!kw) { alert('키워드를 입력해주세요!'); return; }
  const btn = document.getElementById('kw-btn');
  const list = document.getElementById('kw-list');
  btn.disabled=true; btn.textContent='⏳ 추천 중...';

  const loadingId = 'loading-' + Date.now();
  const loadingCard = document.createElement('div');
  loadingCard.id = loadingId;
  loadingCard.className = 'loading';
  loadingCard.style.cssText = 'border:1px solid #f3f4f6;border-radius:12px;padding:20px;margin-bottom:12px';
  loadingCard.innerHTML = '<div class="spinner"></div>릴스 주제 추천 중... (30초~1분 소요)';
  list.insertBefore(loadingCard, list.firstChild);
  list.querySelectorAll('.result-empty').forEach(e=>e.remove());

  const now = new Date().toLocaleTimeString('ko-KR', {hour:'2-digit',minute:'2-digit'});

  try {
    const r = await fetch('/api/content_ai/keyword_reels', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({keyword:kw, category:document.getElementById('kw-category').value})
    });
    const d = await r.json();
    if (!d.success) throw new Error(d.error);
    const recs = d.data.recommendations || [];

    const card = document.createElement('div');
    card.style.cssText = 'border:1px solid #f3f4f6;border-radius:12px;padding:20px;margin-bottom:16px;background:#fff;box-shadow:0 2px 8px rgba(0,0,0,.04)';
    const kwUid = Date.now();
    card.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px">
        <div>
          <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:4px">
            <span class="badge" style="font-size:12px">${kw}</span>
            <span style="font-size:11px;color:#9ca3af">${recs.length}개 추천 · ${now}</span>
          </div>
        </div>
        <button onclick="this.closest('div[style]').remove();updateCount('kw')" style="font-size:13px;color:#9ca3af;border:none;background:none;cursor:pointer">✕</button>
      </div>
      <div style="display:flex;flex-direction:column;gap:12px">
        ${recs.map((r,i)=>`
          <div style="background:#fafafa;border-radius:8px;padding:14px">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
              <span style="background:#C9956C;color:#fff;border-radius:50%;width:20px;height:20px;display:inline-flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;flex-shrink:0">${i+1}</span>
              <span style="font-size:14px;font-weight:700;color:#1A1A1A">${r.title||''}</span>
            </div>
            <div style="font-size:13px;color:#C9956C;font-weight:600;margin-bottom:8px;padding:6px 10px;background:#fff8f5;border-radius:6px">${r.hook||''}</div>
            <div style="font-size:12px;color:#374151;margin-bottom:8px;line-height:1.8">${(r.points||[]).map(p=>`• ${p}`).join('<br>')}</div>
            <div style="font-size:12px;cursor:pointer;color:#9ca3af;margin-bottom:6px" onclick="const sc=this.nextElementSibling;sc.style.display=sc.style.display==='none'?'block':'none';this.textContent=sc.style.display==='none'?'▶ 30초 대본 보기':'▼ 대본 접기'">▶ 30초 대본 보기</div>
            <div style="display:none;font-size:12px;background:#fff;border-radius:6px;padding:12px;line-height:2;white-space:pre-wrap;color:#1A1A1A">${r.script_30sec||''}</div>
            <div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:8px">
              ${(r.hashtags||[]).map(h=>`<span class="htag" style="font-size:11px" onclick="copyText('${h}')">${h}</span>`).join('')}
            </div>
          </div>`).join('')}
      </div>
      ${makeStageBar(kwUid)}
    `;

    list.replaceChild(card, document.getElementById(loadingId));
    updateCount('kw');

  } catch(e) {
    const errCard = document.createElement('div');
    errCard.style.cssText = 'border:1px solid #fee2e2;border-radius:12px;padding:16px;margin-bottom:12px;color:#ef4444;font-size:13px';
    errCard.innerHTML = `오류: ${e.message} <button onclick="this.parentElement.remove()" style="margin-left:8px;border:none;background:none;cursor:pointer;color:#9ca3af">✕</button>`;
    list.replaceChild(errCard, document.getElementById(loadingId));
  } finally {
    btn.disabled=false; btn.textContent='🔑 주제 추천받기';
  }
}

async function generateShorts() {
  const btn = document.getElementById('shorts-btn');
  const list = document.getElementById('shorts-list');
  const count = document.getElementById('shorts-count').value;
  btn.disabled=true; btn.textContent='⏳ 생성 중... (1-2분 소요)';
  btn.style.background='#6b7280';

  const loadingId = 'loading-' + Date.now();
  const loadingCard = document.createElement('div');
  loadingCard.id = loadingId;
  loadingCard.className = 'loading';
  loadingCard.style.cssText = 'border:1px solid #f3f4f6;border-radius:12px;padding:20px;margin-bottom:12px';
  loadingCard.innerHTML = `<div class="spinner"></div>숏츠 ${count}개 생성 중...`;
  list.insertBefore(loadingCard, list.firstChild);
  list.querySelectorAll('.result-empty').forEach(e=>e.remove());

  const now = new Date().toLocaleTimeString('ko-KR', {hour:'2-digit',minute:'2-digit'});

  try {
    const r = await fetch('/api/content_ai/shorts_batch',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({count:parseInt(count)})
    });
    const d = await r.json();
    if (!d.success) throw new Error(d.error);
    const shorts = d.data.shorts || [];

    const card = document.createElement('div');
    card.style.cssText = 'border:1px solid #f3f4f6;border-radius:12px;padding:20px;margin-bottom:16px;background:#fff;box-shadow:0 2px 8px rgba(0,0,0,.04)';
    const sUid = Date.now();
    card.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px">
        <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
          <span class="badge" style="font-size:12px">숏츠 ${shorts.length}개</span>
          <span style="font-size:11px;color:#9ca3af">${now}</span>
        </div>
        <button onclick="this.closest('div[style]').remove();updateCount('shorts')" style="font-size:13px;color:#9ca3af;border:none;background:none;cursor:pointer">✕</button>
      </div>
      <div style="display:flex;flex-direction:column;gap:10px">
        ${shorts.map((s,i)=>`
          <div style="background:#fafafa;border-radius:8px;padding:14px">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
              <span style="background:#C9956C;color:#fff;border-radius:50%;width:20px;height:20px;display:inline-flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;flex-shrink:0">${s.id||i+1}</span>
              <span class="pcat ${(s.category||'').includes('눈')?'eye':(s.category||'').includes('코')?'nose':'lifting'}" style="font-size:11px">${s.category||''}</span>
              <span style="font-size:13px;font-weight:700;color:#1A1A1A">${s.title||''}</span>
            </div>
            <div style="font-size:13px;color:#C9956C;font-weight:600;margin-bottom:8px;padding:6px 10px;background:#fff8f5;border-radius:6px">${s.hook||''}</div>
            <div style="font-size:12px;cursor:pointer;color:#9ca3af;margin-bottom:6px" onclick="const sc=this.nextElementSibling;sc.style.display=sc.style.display==='none'?'block':'none';this.textContent=sc.style.display==='none'?'▶ 대본 보기':'▼ 대본 접기'">▶ 대본 보기</div>
            <div style="display:none;font-size:12px;background:#fff;border-radius:6px;padding:12px;line-height:2;white-space:pre-wrap;color:#1A1A1A">${(s.script_30sec||'')}</div>
            <div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:8px">
              ${(s.hashtags||[]).map(h=>`<span class="htag" style="font-size:11px" onclick="copyText('${h}')">${h}</span>`).join('')}
            </div>
          </div>`).join('')}
      </div>
      ${makeStageBar(sUid)}
    `;

    list.replaceChild(card, document.getElementById(loadingId));
    updateCount('shorts');

    btn.style.background='#16a34a';
    btn.textContent='✅ 생성 완료!';
    setTimeout(()=>{btn.style.background='linear-gradient(135deg,#C9956C,#E8927C)';btn.textContent='⚡ 숏츠 생성';},3000);
  } catch(e) {
    const errCard = document.createElement('div');
    errCard.style.cssText = 'border:1px solid #fee2e2;border-radius:12px;padding:16px;margin-bottom:12px;color:#ef4444;font-size:13px';
    errCard.innerHTML = `오류: ${e.message} <button onclick="this.parentElement.remove()" style="margin-left:8px;border:none;background:none;cursor:pointer;color:#9ca3af">✕</button>`;
    list.replaceChild(errCard, document.getElementById(loadingId));
    btn.style.background='linear-gradient(135deg,#C9956C,#E8927C)';
    btn.textContent='⚡ 숏츠 생성';
  } finally {
    btn.disabled=false;
  }
}

async function loadHistory() {
  const el = document.getElementById('history-list');
  try {
    const r = await fetch('/api/content_ai/history');
    const items = await r.json();
    if (!items.length) {
      el.innerHTML='<div class="result-empty">아직 생성된 콘텐츠가 없어요</div>';
      return;
    }
    const typeLabel = {youtube:'🎬 유튜브',shorts_batch:'⚡ 숏츠',face:'👤 얼굴분석',keyword_reels:'🔑 키워드 릴스'};
    el.innerHTML = `
      <table style="width:100%;border-collapse:collapse;font-size:13px">
        <thead>
          <tr style="border-bottom:2px solid #f3f4f6">
            <th style="padding:10px;text-align:left;color:#6b7280;font-weight:600">유형</th>
            <th style="padding:10px;text-align:left;color:#6b7280;font-weight:600">내용</th>
            <th style="padding:10px;text-align:left;color:#6b7280;font-weight:600">생성일시</th>
          </tr>
        </thead>
        <tbody>
          ${items.map(i=>`
            <tr style="border-bottom:1px solid #f9fafb">
              <td style="padding:10px">${typeLabel[i.type]||i.type}</td>
              <td style="padding:10px;color:#1A1A1A">${i.preview||i.keyword||i.category||'-'}</td>
              <td style="padding:10px;color:#9ca3af">${i.created_at||''}</td>
            </tr>`).join('')}
        </tbody>
      </table>`;
  } catch(e) {
    el.innerHTML='<div class="result-empty" style="color:#ef4444">로드 실패</div>';
  }
}

function toggleScript(el) {
  const sc = el.nextElementSibling;
  if (sc.style.display==='block') { sc.style.display='none'; el.textContent='▶ 30초 대본 보기'; }
  else { sc.style.display='block'; el.textContent='▼ 30초 대본 접기'; }
}
</script>
</body>
</html>
"""

@app.route('/content_ai')
def content_ai_page():
    return render_template_string(CONTENT_AI_HTML)


# ════════════════════════════════════════════
# 자동화 파이프라인 API - 점유율 진단 -> GEO 콘텐츠 작성 -> 콘텐츠 발행
# ════════════════════════════════════════════

@app.route("/api/auto/run", methods=["POST"])
def api_auto_run():
    """3단계 자동화 파이프라인 실행"""
    import subprocess as _sp
    import threading as _th

    steps_result = {
        "step1_sov": {"status": "pending"},
        "step2_content": {"status": "pending"},
        "step3_publish": {"status": "pending"},
    }

    date_str = datetime.now().strftime("%Y%m%d")
    log_file = BASE_DIR / "output" / "auto_run_log.json"

    def run_pipeline():
        # STEP 1: SOV 점유율 진단
        try:
            steps_result["step1_sov"]["status"] = "running"
            save_auto_log(log_file, steps_result)

            # 프롬프트 생성
            r1 = _sp.run(["python", "prompt_gen.py"], cwd=str(BASE_DIR),
                        capture_output=True, text=True, timeout=120)
            # SOV 측정
            r2 = _sp.run(["python", "sov_tracker.py"], cwd=str(BASE_DIR),
                        capture_output=True, text=True, timeout=600)
            steps_result["step1_sov"]["status"] = "done" if r2.returncode == 0 else "error"
            steps_result["step1_sov"]["output"] = r2.stdout[-200:]
        except Exception as e:
            steps_result["step1_sov"]["status"] = "error"
            steps_result["step1_sov"]["error"] = str(e)
        save_auto_log(log_file, steps_result)

        # STEP 2: GEO 콘텐츠 작성 (블로그 + 매거진)
        try:
            steps_result["step2_content"]["status"] = "running"
            save_auto_log(log_file, steps_result)

            r3 = _sp.run(["python", "run.py"], cwd=str(BASE_DIR),
                        capture_output=True, text=True, timeout=900)
            r4 = _sp.run(["python", "magazine_run.py"], cwd=str(BASE_DIR / ".."),
                        capture_output=True, text=True, timeout=900)
            steps_result["step2_content"]["status"] = "done"
            steps_result["step2_content"]["blog"] = r3.returncode == 0
            steps_result["step2_content"]["magazine"] = r4.returncode == 0
        except Exception as e:
            steps_result["step2_content"]["status"] = "error"
            steps_result["step2_content"]["error"] = str(e)
        save_auto_log(log_file, steps_result)

        # STEP 3: 콘텐츠 발행 완료 표시
        try:
            steps_result["step3_publish"]["status"] = "running"
            save_auto_log(log_file, steps_result)
            # 발행 준비 완료 (네이버 업로드는 수동)
            steps_result["step3_publish"]["status"] = "done"
            steps_result["step3_publish"]["message"] = "발행 준비 완료. 네이버 블로그 업로드 탭에서 진행하세요."
        except Exception as e:
            steps_result["step3_publish"]["status"] = "error"
        save_auto_log(log_file, steps_result)

    def save_auto_log(path, data):
        try:
            path.write_text(json.dumps({
                "date": datetime.now().isoformat(),
                "steps": data
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    # 백그라운드 실행
    t = _th.Thread(target=run_pipeline, daemon=True)
    t.start()

    return jsonify({"success": True, "message": "자동화 파이프라인 시작됨"})


@app.route("/api/auto/status")
def api_auto_status():
    """자동화 파이프라인 진행 상태 확인"""
    log_file = BASE_DIR / "output" / "auto_run_log.json"
    if log_file.exists():
        try:
            return jsonify(json.loads(log_file.read_text(encoding="utf-8")))
        except Exception:
            pass
    return jsonify({"steps": {
        "step1_sov": {"status": "pending"},
        "step2_content": {"status": "pending"},
        "step3_publish": {"status": "pending"},
    }})


@app.route("/api/content_ai/shorts_batch", methods=["POST"])
def api_shorts_batch():
    """숏츠 10개 한 번에 생성 - 주제 중복 없이"""
    try:
        import anthropic as _ant
        data = request.get_json() or {}
        count = data.get("count", 10)

        # 기존 생성된 주제 로드 (중복 방지)
        used_topics = []
        for f in CONTENT_AI_DIR.glob("*_shorts_*.json"):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                for item in d.get("result", {}).get("shorts", []):
                    used_topics.append(item.get("title", ""))
            except Exception:
                pass

        used_str = "\n".join(used_topics[:30]) if used_topics else "없음"

        prompt = f"""당신은 팝성형외과 인스타그램 숏츠 전문 기획자입니다.

[의료법 준수 - 절대 규칙]
1. 효과 보장/최상급 표현 금지
2. 전후 비교/치료경험담 금지
3. 부정적 외모 평가 금지
4. 타 병원 비교/비방 금지
5. 유인성 표현 금지

[이미 생성된 주제 - 중복 금지]
{used_str}

[요청]
팝성형외과 인스타그램 숏츠 주제 {count}개를 생성하세요.
- 눈성형/코성형/리프팅 자유 비율
- 각 주제마다 완전히 다른 각도 (오해와진실/심리/비교/주의사항/나이노화/타이밍 등)
- 위 중복 주제와 겹치지 않게
- 30초 대본 포함

JSON으로만 응답:
{{
  "shorts": [
    {{
      "id": 1,
      "category": "눈성형/코성형/리프팅",
      "angle": "각도",
      "title": "숏츠 제목",
      "hook": "첫 1-2초 훅 (12자 이내)",
      "script_30sec": "30초 대본 (문장 끊음 포함\n마디마다 / 표시)",
      "hashtags": ["#태그1", "#태그2", "#태그3"]
    }}
  ]
}}
"""

        client = _ant.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY",""))
        resp = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=4000,
            messages=[{"role":"user","content":prompt}]
        )
        raw = resp.content[0].text.strip()
        raw = raw.replace("```json","").replace("```","").strip()
        if raw.find('{') >= 0:
            raw = raw[raw.find('{'):raw.rfind('}')+1]
        elif raw.find('[') >= 0:
            raw = '{"shorts":' + raw[raw.find('['):raw.rfind(']')+1] + '}'
        try:
            result = json.loads(raw)
        except Exception:
            result = {"shorts": [{"id":1,"category":"눈성형","angle":"","title":"파싱 오류","hook":"","script_30sec":raw[:200],"hashtags":[]}]}

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = CONTENT_AI_DIR / f"{ts}_shorts_batch.json"
        out.write_text(json.dumps({
            "type":"shorts_batch","count":count,
            "created_at":datetime.now().isoformat(),"result":result
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        return jsonify({"success":True,"data":result})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})


@app.route("/api/content_ai/history")
def api_content_ai_history():
    """생성된 콘텐츠 전체 히스토리"""
    try:
        files = sorted(CONTENT_AI_DIR.glob("*.json"),
                      key=lambda f: f.stat().st_mtime, reverse=True)
        items = []
        for f in files[:100]:
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                result = d.get("result", {})
                preview = ""
                if d.get("type") == "youtube":
                    preview = (result.get("titles",{}).get("seo","") or
                              result.get("longform","")[:50])
                elif d.get("type") == "shorts_batch":
                    shorts = result.get("shorts",[])
                    preview = f"{len(shorts)}개 생성"
                elif d.get("type") == "face":
                    preview = result.get("face_type","")
                elif d.get("type") == "keyword_reels":
                    preview = f"{len(result.get('recommendations',[]))}개 추천"

                items.append({
                    "filename": f.name,
                    "type": d.get("type",""),
                    "category": d.get("category",""),
                    "keyword": d.get("keyword",""),
                    "created_at": d.get("created_at","")[:16],
                    "preview": preview,
                })
            except Exception:
                continue
        return jsonify(items)
    except Exception as e:
        return jsonify({"error":str(e)})


if __name__ == '__main__':
    import os as _os
    port = int(_os.environ.get("PORT", 5000))
    print("\n" + "="*40)
    print("팝성형외과 콘텐츠 AI 서버")
    print(f"포트: {port}")
    print("="*40 + "\n")
    app.run(debug=False, port=port, host='0.0.0.0')
