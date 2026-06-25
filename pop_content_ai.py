import os, json, random
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify

app = Flask(__name__)
BASE_DIR = Path(__file__).parent
OUT_DIR = BASE_DIR / "output" / "content_ai"
OUT_DIR.mkdir(parents=True, exist_ok=True)

ANGLES = ["오해와 진실","비교와 선택","주의사항","회복과 관리","타이밍과 시기",
    "심리와 감정","후회와 재수술","나이와 노화","원장 시각","케이스 분석",
    "숫자와 데이터","Q&A 답변","부작용과 위험","트렌드 분석","하면 안 되는 경우",
    "자연스러움의 기준","처음 하는 사람 가이드","시즌별 가이드"]

def next_angle(cat):
    used = []
    for f in OUT_DIR.glob(f"*_yt_{cat}*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            if d.get("angle"): used.append(d["angle"])
        except: pass
    pool = [a for a in ANGLES if a not in used] or ANGLES
    return random.choice(pool)

@app.route("/")
@app.route("/content_ai")
def index():
    return app.response_class(PAGE, mimetype="text/html; charset=utf-8")

@app.route("/api/youtube", methods=["POST"])
def api_youtube():
    try:
        import anthropic
        data = request.json or {}
        cat = data.get("category","눈성형")
        vtype = data.get("type","롱폼")
        angle = next_angle(cat)

        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY",""))

        r1 = client.messages.create(model="claude-sonnet-4-6", max_tokens=3000,
            messages=[{"role":"user","content":f"""팝성형외과 유튜브 {vtype} 스크립트.
카테고리: {cat} / 각도: {angle}
규칙: 해요체, 친근한 전문의 말투, 문장마다 / 로 끊음
인사: 안녕하세요, 팝성형외과 000 원장입니다.
마무리: 지금까지 팝성형외과 000 원장이었습니다.
마지막줄: *본 콘텐츠는 AI 기반 도구의 도움을 받아 제작되었으며, 진단치료를 대체하지 않습니다.
의료법: 효과보장/전후비교/최상급/타병원비교 금지. 부작용 언급 필수.
{"3분 분량 1000~1200자" if "롱폼" in vtype else "30초 분량 200자"}
인기영상 벤치마킹: 첫 문장에 핵심 결론. 역설/반전 후킹. 케이스1->2->3 순서. 단점 솔직히.
[0:00 후킹] [0:15 인사] [0:25 본론] [2:30 마무리]
스크립트만 출력."""}])
        longform = r1.content[0].text.strip()

        r2 = client.messages.create(model="claude-sonnet-4-6", max_tokens=1000,
            messages=[{"role":"user","content":f"""스크립트 메타데이터 JSON으로만 출력. 번역은 현지인 자연스러운 표현.
카테고리: {cat}, 각도: {angle}
스크립트: {longform[:300]}...
{{"title_seo":"","title_curiosity":"","title_empathy":"","thumbnail1":"","thumbnail2":"","thumbnail3":"","hook1":"","hook2":"","hook3":"","hashtags":"#태그1 #태그2 #태그3 #태그4 #태그5 #태그6 #태그7 #태그8 #태그9 #태그10","description":"","en":{{"title":"","thumbnail":"","hashtags":"#tag1 #tag2 #tag3 #tag4 #tag5"}},"zh":{{"title":"","thumbnail":"","hashtags":"#标签1 #标签2 #标签3 #标签4 #标签5"}},"ja":{{"title":"","thumbnail":"","hashtags":"#タグ1 #タグ2 #タグ3 #タグ4 #タグ5"}}}}"""}])
        raw = r2.content[0].text.strip().replace("```json","").replace("```","").strip()
        if "{" in raw: raw = raw[raw.find("{"):raw.rfind("}")+1]
        try: meta = json.loads(raw)
        except: meta = {}

        r3 = client.messages.create(model="claude-sonnet-4-6", max_tokens=1500,
            messages=[{"role":"user","content":f"""롱폼에서 30초 숏폼 4개 추출. 문장 / 로 끊기.
롱폼: {longform}
JSON 배열만 출력:
[{{"id":1,"hook":"훅","script":"내용 / 내용 / 내용","thumbnail_text":"썸네일"}},{{"id":2,"hook":"훅","script":"내용 / 내용 / 내용","thumbnail_text":"썸네일"}},{{"id":3,"hook":"훅","script":"내용 / 내용 / 내용","thumbnail_text":"썸네일"}},{{"id":4,"hook":"훅","script":"내용 / 내용 / 내용","thumbnail_text":"썸네일"}}]"""}])
        sraw = r3.content[0].text.strip().replace("```json","").replace("```","").strip()
        if "[" in sraw: sraw = sraw[sraw.find("["):sraw.rfind("]")+1]
        try: shorts = json.loads(sraw)
        except: shorts = []

        result = {"angle":angle,"longform":longform,"shortforms":shorts,
            "titles":{"seo":meta.get("title_seo",""),"curiosity":meta.get("title_curiosity",""),"empathy":meta.get("title_empathy","")},
            "thumbnails":[{"text":meta.get("thumbnail1","")},{"text":meta.get("thumbnail2","")},{"text":meta.get("thumbnail3","")}],
            "hashtags":meta.get("hashtags","").split(),"hooks":[meta.get("hook1",""),meta.get("hook2",""),meta.get("hook3","")],
            "description":meta.get("description",""),"multilang":{"en":meta.get("en",{}),"zh":meta.get("zh",{}),"ja":meta.get("ja",{})}}

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        (OUT_DIR/f"{ts}_yt_{cat}.json").write_text(json.dumps({"type":"youtube","category":cat,"angle":angle,"created_at":datetime.now().isoformat(),"result":result},ensure_ascii=False,indent=2),encoding="utf-8")
        return jsonify({"success":True,"data":result})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})

@app.route("/api/shorts", methods=["POST"])
def api_shorts():
    try:
        import anthropic
        data = request.json or {}
        count = data.get("count",10)
        used = []
        for f in OUT_DIR.glob("*_shorts*.json"):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                for s in d.get("result",{}).get("shorts",[]):
                    used.append(s.get("title",""))
            except: pass
        used_str = "\n".join(used[:30]) if used else "없음"
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY",""))
        resp = client.messages.create(model="claude-sonnet-4-6", max_tokens=4000,
            messages=[{"role":"user","content":f"""팝성형외과 숏츠 {count}개 생성. 의료법 준수.
이미 생성된 주제(중복 금지): {used_str}
눈/코/리프팅 자유 비율. 각각 다른 각도.
JSON만 출력: {{"shorts":[{{"id":1,"category":"눈성형","angle":"각도","title":"제목","hook":"훅","script_30sec":"대본","hashtags":["#태그"]}}]}}"""}])
        raw = resp.content[0].text.strip().replace("```json","").replace("```","").strip()
        if "{" in raw: raw = raw[raw.find("{"):raw.rfind("}")+1]
        try: result = json.loads(raw)
        except: result = {"shorts":[]}
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        (OUT_DIR/f"{ts}_shorts.json").write_text(json.dumps({"type":"shorts_batch","created_at":datetime.now().isoformat(),"result":result},ensure_ascii=False,indent=2),encoding="utf-8")
        return jsonify({"success":True,"data":result})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})

@app.route("/api/face", methods=["POST"])
def api_face():
    try:
        import anthropic
        data = request.json or {}
        b64 = data.get("image_base64","")
        mtype = data.get("media_type","image/jpeg")
        mode = data.get("mode","concern")
        if not b64: return jsonify({"success":False,"error":"이미지 없음"})
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY",""))
        prompt = f"""팝성형외과 {'연예인 얼굴 변화 분석' if mode=='celebrity' else '얼굴형 분석'} 릴스 대본.
의료법 준수. 부정적 외모 평가 금지.
JSON만 출력: {{"face_type":"","face_features":"","strength":"","hook":"","reels_script":{{"0-3초":"","3-10초":"","10-50초":"","50-60초":""}},"caption":"","hashtags":["#팝성형외과","#강남성형외과"]}}"""
        resp = client.messages.create(model="claude-sonnet-4-6", max_tokens=1500,
            messages=[{"role":"user","content":[{"type":"image","source":{"type":"base64","media_type":mtype,"data":b64}},{"type":"text","text":prompt}]}])
        raw = resp.content[0].text.strip().replace("```json","").replace("```","").strip()
        if "{" in raw: raw = raw[raw.find("{"):raw.rfind("}")+1]
        try: result = json.loads(raw)
        except: result = {"face_type":"분석완료","face_features":raw[:200],"strength":"","hook":"","reels_script":{},"caption":"","hashtags":[]}
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        (OUT_DIR/f"{ts}_face.json").write_text(json.dumps({"type":"face","mode":mode,"created_at":datetime.now().isoformat(),"result":result},ensure_ascii=False,indent=2),encoding="utf-8")
        return jsonify({"success":True,"data":result})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})

@app.route("/api/keyword", methods=["POST"])
def api_keyword():
    try:
        import anthropic
        data = request.json or {}
        kw = data.get("keyword","")
        cat = data.get("category","눈성형")
        if not kw: return jsonify({"success":False,"error":"키워드 없음"})
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY",""))
        resp = client.messages.create(model="claude-sonnet-4-6", max_tokens=2000,
            messages=[{"role":"user","content":f"""팝성형외과 릴스 주제 5개 추천. 키워드: {kw}, 카테고리: {cat}. 의료법 준수.
JSON만 출력: {{"recommendations":[{{"id":1,"title":"","hook":"","points":["",""],"script_30sec":"","hashtags":["#태그"]}}]}}"""}])
        raw = resp.content[0].text.strip().replace("```json","").replace("```","").strip()
        if "{" in raw: raw = raw[raw.find("{"):raw.rfind("}")+1]
        try: result = json.loads(raw)
        except: result = {"recommendations":[]}
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        (OUT_DIR/f"{ts}_kw_{kw[:20]}.json").write_text(json.dumps({"type":"keyword_reels","keyword":kw,"created_at":datetime.now().isoformat(),"result":result},ensure_ascii=False,indent=2),encoding="utf-8")
        return jsonify({"success":True,"data":result})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})

@app.route("/api/history")
def api_history():
    try:
        files = sorted(OUT_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        items = []
        for f in files[:50]:
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                r = d.get("result",{})
                preview = ""
                t = d.get("type","")
                if t=="youtube": preview = r.get("titles",{}).get("seo","")[:40]
                elif t=="shorts_batch": preview = f"{len(r.get('shorts',[]))}개 생성"
                elif t=="face": preview = r.get("face_type","")
                elif t=="keyword_reels": preview = f"{len(r.get('recommendations',[]))}개 추천"
                items.append({"type":t,"preview":preview,"keyword":d.get("keyword",""),"category":d.get("category",""),"created_at":d.get("created_at","")[:16]})
            except: pass
        return jsonify(items)
    except Exception as e:
        return jsonify([])

PAGE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>POP 콘텐츠 AI</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI','Noto Sans KR',sans-serif;background:#0f0f1a;color:#fff}
.hdr{background:linear-gradient(135deg,#1a1a2e,#16213e);padding:18px 28px;border-bottom:1px solid #2a2a3e}
.hdr h1{font-size:18px;font-weight:700;color:#C9956C}
.hdr p{font-size:12px;color:#6b7280;margin-top:3px}
.tabs{display:flex;gap:4px;padding:10px 28px;background:#0f0f1a;border-bottom:1px solid #1a1a2e;overflow-x:auto}
.tab{padding:7px 16px;border-radius:8px;font-size:12px;font-weight:600;cursor:pointer;border:none;background:#1a1a2e;color:#9ca3af;white-space:nowrap;transition:all .15s}
.tab.on{background:#C9956C;color:#fff}
.body{display:flex;height:calc(100vh - 108px)}
.side{width:260px;min-width:260px;background:#1a1a2e;padding:18px;border-right:1px solid #2a2a3e;overflow-y:auto}
.res{flex:1;padding:18px;overflow-y:auto}
.panel{display:none}
.panel.on{display:flex;width:100%}
.stitle{font-size:10px;font-weight:700;color:#C9956C;text-transform:uppercase;letter-spacing:.06em;margin:14px 0 6px}
.fg{margin-bottom:12px}
.lbl{font-size:11px;color:#9ca3af;display:block;margin-bottom:4px}
select,input[type=text]{width:100%;padding:8px 10px;border-radius:7px;border:1px solid #2a2a3e;background:#0f0f1a;color:#fff;font-size:12px;outline:none}
.btn{width:100%;padding:10px;border-radius:8px;font-size:13px;font-weight:700;cursor:pointer;border:none;background:#C9956C;color:#fff;margin-top:6px;transition:opacity .15s}
.btn:disabled{opacity:.4;cursor:not-allowed}
.empty{display:flex;flex-direction:column;align-items:center;justify-content:center;height:250px;color:#4b5563;gap:10px;font-size:13px}
.card{background:#1a1a2e;border:1px solid #2a2a3e;border-radius:10px;padding:16px;margin-bottom:12px}
.ld{background:#1a1a2e;border:1px solid #2a2a3e;border-radius:10px;padding:20px;margin-bottom:12px;color:#9ca3af;font-size:12px;display:flex;align-items:center;gap:10px}
.spin{width:16px;height:16px;border:2px solid #2a2a3e;border-top-color:#C9956C;border-radius:50%;animation:sp .7s linear infinite;flex-shrink:0}
@keyframes sp{to{transform:rotate(360deg)}}
.err{background:#1a1a2e;border:1px solid #ef444450;border-radius:10px;padding:14px;margin-bottom:12px;color:#f87171;font-size:12px;display:flex;justify-content:space-between;align-items:center}
.bdg{display:inline-block;padding:2px 8px;border-radius:12px;font-size:10px;font-weight:600;margin-right:3px}
.b1{background:#C9956C20;color:#C9956C;border:1px solid #C9956C40}
.b2{background:#4f46e520;color:#818cf8;border:1px solid #4f46e540}
.b3{background:#c026d320;color:#e879f9;border:1px solid #c026d340}
.sbox{background:#0f0f1a;border:1px solid #2a2a3e;border-radius:7px;padding:11px;font-size:11px;line-height:1.95;color:#d1d5db;white-space:pre-wrap;max-height:220px;overflow-y:auto;margin:6px 0}
.cpbtn{padding:3px 9px;border-radius:5px;font-size:10px;cursor:pointer;border:1px solid #2a2a3e;background:#0f0f1a;color:#9ca3af;transition:all .15s}
.cpbtn:hover{border-color:#C9956C;color:#C9956C}
.sfgrid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.sfcard{background:#0f0f1a;border:1px solid #2a2a3e;border-radius:7px;padding:10px}
.htag{display:inline-block;padding:2px 7px;border-radius:10px;font-size:10px;cursor:pointer;background:#1a1a2e;color:#9ca3af;border:1px solid #2a2a3e;margin:2px;transition:all .15s}
.htag:hover{border-color:#C9956C;color:#C9956C}
.sbar{display:flex;gap:4px;margin-top:10px;padding-top:10px;border-top:1px solid #2a2a3e;flex-wrap:wrap}
.sbtn{padding:3px 9px;border-radius:12px;font-size:10px;font-weight:600;border:1px solid #2a2a3e;background:#0f0f1a;color:#6b7280;cursor:pointer;transition:all .15s}
.sbtn.done{background:#16a34a;border-color:#16a34a;color:#fff}
.sbtn.cur{background:#C9956C;border-color:#C9956C;color:#fff}
.exbtn{font-size:10px;color:#6b7280;cursor:pointer;padding:3px 0;display:block;margin-top:4px}
.exbox{display:none;margin-top:5px}
.uparea{border:2px dashed #2a2a3e;border-radius:7px;padding:14px;text-align:center;cursor:pointer;margin-bottom:8px}
.uparea:hover{border-color:#C9956C}
.tbl{width:100%;border-collapse:collapse;font-size:12px}
.tbl th{padding:9px 10px;text-align:left;color:#6b7280;border-bottom:1px solid #2a2a3e;font-weight:600}
.tbl td{padding:9px 10px;border-bottom:1px solid #1a1a2e;color:#d1d5db}
.langbox{background:#0f0f1a;border:1px solid #2a2a3e;border-radius:7px;padding:10px;margin-bottom:6px}
.row{display:flex;justify-content:space-between;align-items:center}
</style>
</head>
<body>
<div class="hdr"><h1>POP 콘텐츠 AI</h1><p>팝성형외과 콘텐츠 자동 생성 시스템</p></div>
<div class="tabs">
  <button class="tab on" id="t-yt" onclick="go('yt',this)">🎬 유튜브 스크립트</button>
  <button class="tab" id="t-sh" onclick="go('sh',this)">⚡ 숏츠 10개</button>
  <button class="tab" id="t-fc" onclick="go('fc',this)">👤 얼굴형 분석</button>
  <button class="tab" id="t-kw" onclick="go('kw',this)">🔑 키워드 릴스</button>
  <button class="tab" id="t-hi" onclick="go('hi',this);loadHi()">📋 히스토리</button>
</div>
<div class="body">

<div class="panel on" id="p-yt">
<div class="side">
  <div class="stitle">설정</div>
  <div class="fg"><label class="lbl">카테고리</label>
    <select id="yc"><option>눈성형</option><option>코성형</option><option>리프팅</option><option>윤곽</option><option>지방이식</option></select>
  </div>
  <div class="fg"><label class="lbl">영상 유형</label>
    <select id="yt"><option value="롱폼">롱폼 3분</option><option value="숏폼 30초">숏폼 30초</option></select>
  </div>
  <button class="btn" id="yb" onclick="genYT()">🎬 스크립트 생성</button>
</div>
<div class="res" id="yr"><div class="empty"><div>🎬</div><div>설정 후 생성 클릭</div></div></div>
</div>

<div class="panel" id="p-sh">
<div class="side">
  <div class="stitle">설정</div>
  <div class="fg"><label class="lbl">생성 개수</label>
    <select id="sn"><option value="10">10개</option><option value="5">5개</option><option value="20">20개</option></select>
  </div>
  <div style="background:#C9956C10;border:1px solid #C9956C30;border-radius:7px;padding:10px;font-size:11px;color:#9ca3af;line-height:1.7;margin-bottom:10px">✨ 기존 주제와 중복 없이 자동 생성</div>
  <button class="btn" id="sb" onclick="genSH()">⚡ 숏츠 생성</button>
</div>
<div class="res" id="sr"><div class="empty"><div>⚡</div><div>버튼 클릭하여 생성</div></div></div>
</div>

<div class="panel" id="p-fc">
<div class="side">
  <div class="stitle">설정</div>
  <div class="fg"><label class="lbl">모드</label>
    <select id="fm" onchange="tfm()"><option value="concern">고민형</option><option value="celebrity">연예인 분석</option></select>
  </div>
  <div id="caw" class="fg"><label class="lbl">고민 부위</label>
    <select id="ca"><option>눈</option><option>코</option><option>입술</option><option>윤곽</option><option>피부</option></select>
  </div>
  <div id="cew" class="fg" style="display:none"><label class="lbl">인물명</label>
    <input type="text" id="pn" placeholder="예: 아이유">
  </div>
  <div class="fg"><label class="lbl">이미지</label>
    <div class="uparea" onclick="document.getElementById('fi').click()" id="fp"><div>📷</div><div style="font-size:11px;color:#6b7280;margin-top:5px">클릭하여 선택</div></div>
    <input type="file" id="fi" accept="image/*" style="display:none" onchange="pfv(this)">
  </div>
  <button class="btn" id="fb" onclick="genFC()">👤 분석 시작</button>
</div>
<div class="res" id="fr"><div class="empty"><div>👤</div><div>이미지 업로드 후 분석</div></div></div>
</div>

<div class="panel" id="p-kw">
<div class="side">
  <div class="stitle">설정</div>
  <div class="fg"><label class="lbl">키워드</label><input type="text" id="ki" placeholder="예: 쌍꺼풀 수술"></div>
  <div class="fg"><label class="lbl">카테고리</label>
    <select id="kc"><option>눈성형</option><option>코성형</option><option>리프팅</option><option>윤곽</option></select>
  </div>
  <button class="btn" id="kb" onclick="genKW()">🔑 주제 추천</button>
</div>
<div class="res" id="kr"><div class="empty"><div>🔑</div><div>키워드 입력 후 추천</div></div></div>
</div>

<div class="panel" id="p-hi">
<div class="res" style="width:100%" id="hr"><div class="empty"><div>📋</div><div>로딩 중...</div></div></div>
</div>

</div>
<script>
var fb64='',ftype='image/jpeg';
var STAGES=['생성완료','촬영완료','편집완료','업로드예정','업로드완료'];

function go(id,btn){
  document.querySelectorAll('.tab').forEach(function(t){t.classList.remove('on')});
  btn.classList.add('on');
  document.querySelectorAll('.panel').forEach(function(p){p.style.display='none';p.classList.remove('on')});
  var el=document.getElementById('p-'+id);
  el.style.display='flex';
  el.classList.add('on');
}
function tfm(){
  var m=document.getElementById('fm').value;
  document.getElementById('caw').style.display=m=='concern'?'block':'none';
  document.getElementById('cew').style.display=m=='celebrity'?'block':'none';
}
function pfv(inp){
  var file=inp.files[0]; if(!file) return;
  ftype=file.type||'image/jpeg';
  var r=new FileReader();
  r.onload=function(e){
    fb64=e.target.result.split(',')[1];
    document.getElementById('fp').innerHTML='<img src="'+e.target.result+'" style="max-width:100%;max-height:130px;border-radius:6px">';
  };
  r.readAsDataURL(file);
}
function cp(txt,btn){
  navigator.clipboard.writeText(txt).then(function(){
    if(btn){var orig=btn.textContent;btn.textContent='✓ 복사됨';setTimeout(function(){btn.textContent=orig},1500)}
  });
}
function esc(s){
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function sb(uid){
  var saved=JSON.parse(localStorage.getItem('st_'+uid)||'{"i":0}');
  var i=saved.i||0;
  var h='<div class="sbar" id="sb_'+uid+'">';
  for(var j=0;j<STAGES.length;j++){
    var c='sbtn'+(j<i?' done':j==i?' cur':'');
    h+='<button class="'+c+'" onclick="ss(\''+uid+'\','+j+')">'+(j<i?'✓ ':'')+STAGES[j]+'</button>';
  }
  return h+'</div>';
}
function ss(uid,i){
  localStorage.setItem('st_'+uid,JSON.stringify({i:i}));
  var bar=document.getElementById('sb_'+uid); if(!bar) return;
  var btns=bar.querySelectorAll('.sbtn');
  for(var j=0;j<btns.length;j++){
    btns[j].className='sbtn'+(j<i?' done':j==i?' cur':'');
    btns[j].textContent=(j<i?'✓ ':'')+STAGES[j];
  }
}
function ld(rid){
  var res=document.getElementById(rid);
  res.querySelectorAll('.empty').forEach(function(e){e.remove()});
  var id='ld'+Date.now();
  var d=document.createElement('div');
  d.id=id; d.className='ld';
  d.innerHTML='<div class="spin"></div>생성 중... (30초~1분 소요)';
  res.insertBefore(d,res.firstChild);
  return id;
}
function err(rid,lid,msg){
  var d=document.createElement('div'); d.className='err';
  d.innerHTML=esc(msg)+'<button class="cpbtn" onclick="this.closest(\'.err\').remove()">닫기</button>';
  var l=document.getElementById(lid);
  if(l) l.replaceWith(d); else document.getElementById(rid).insertBefore(d,document.getElementById(rid).firstChild);
}

async function genYT(){
  var btn=document.getElementById('yb');
  btn.disabled=true; btn.textContent='⏳ 생성 중...';
  var lid=ld('yr');
  var cat=document.getElementById('yc').value;
  var type=document.getElementById('yt').value;
  var now=new Date().toLocaleTimeString('ko-KR',{hour:'2-digit',minute:'2-digit'});
  var uid=''+Date.now();
  try{
    var resp=await fetch('/api/youtube',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({category:cat,type:type})});
    var d=await resp.json();
    if(!d.success) throw new Error(d.error);
    var v=d.data;
    var sf=(v.shortforms||[]).map(function(s,i){
      return '<div class="sfcard"><div style="font-size:10px;font-weight:700;color:#C9956C;margin-bottom:3px">숏폼 '+(i+1)+'</div>'
        +(s.hook?'<div style="font-size:11px;color:#e879f9;margin-bottom:5px;padding:4px 7px;background:#c026d310;border-radius:5px">'+esc(s.hook)+'</div>':'')
        +'<div style="font-size:10px;line-height:1.9;color:#d1d5db;white-space:pre-wrap" id="sf'+uid+'i'+i+'">'+esc(s.script||'')+'</div>'
        +'<button class="cpbtn" style="margin-top:5px" onclick="cp(document.getElementById(\'sf'+uid+'i'+i+'\').textContent,this)">복사</button></div>';
    }).join('');
    var ml=v.multilang||{};
    var mlh='';
    if(ml.en&&ml.en.title||ml.zh&&ml.zh.title||ml.ja&&ml.ja.title){
      mlh='<div class="stitle" style="margin-top:10px">🌐 다국어</div>';
      var langs=[['en','🇺🇸','English'],['zh','🇨🇳','中文'],['ja','🇯🇵','日本語']];
      for(var i=0;i<langs.length;i++){
        var lg=langs[i]; var ld2=ml[lg[0]]||{};
        if(!ld2.title) continue;
        mlh+='<div class="langbox"><div style="font-size:11px;font-weight:700;margin-bottom:5px">'+lg[1]+' '+lg[2]+'</div>'
          +'<div style="font-size:12px;font-weight:600;color:#f3f4f6;margin-bottom:3px" id="lt'+uid+lg[0]+'">'+esc(ld2.title||'')+'</div>'
          +'<div style="font-size:11px;color:#6b7280;margin-bottom:5px">'+esc(ld2.thumbnail||'')+'</div>'
          +'<div>'+((ld2.hashtags||'').split(' ').filter(function(h){return h}).map(function(h){return '<span class="htag" onclick="cp(\''+h+'\',null)">'+esc(h)+'</span>'}).join(''))+'</div>'
          +'<button class="cpbtn" style="margin-top:5px" onclick="cp(document.getElementById(\'lt'+uid+lg[0]+'\').textContent,this)">제목복사</button></div>';
      }
    }
    var card=document.createElement('div'); card.className='card';
    card.innerHTML=
      '<div class="row" style="margin-bottom:10px">'
        +'<div><span class="bdg b1">'+esc(cat)+'</span><span class="bdg b2">'+esc(type)+'</span>'
        +(v.angle?'<span class="bdg b3">📐 '+esc(v.angle)+'</span>':'')
        +'<span style="font-size:10px;color:#4b5563;margin-left:5px">'+now+'</span></div>'
        +'<button class="cpbtn" onclick="this.closest(\'.card\').remove()">✕</button>'
      +'</div>'
      +'<div class="stitle">제목</div>'
      +'<div style="margin-bottom:8px">'
        +'<div style="display:flex;align-items:center;gap:7px;margin-bottom:4px">'
          +'<span style="background:#3b82f620;color:#60a5fa;padding:2px 6px;border-radius:4px;font-size:9px;font-weight:700">SEO</span>'
          +'<span style="font-size:12px;font-weight:600;color:#f3f4f6" id="ts'+uid+'">'+esc(v.titles&&v.titles.seo||'')+'</span>'
          +'<button class="cpbtn" onclick="cp(document.getElementById(\'ts'+uid+'\').textContent,this)">복사</button>'
        +'</div>'
        +'<div style="font-size:11px;color:#9ca3af;margin-bottom:2px">'+esc(v.titles&&v.titles.curiosity||'')+'</div>'
        +'<div style="font-size:11px;color:#9ca3af">'+esc(v.titles&&v.titles.empathy||'')+'</div>'
      +'</div>'
      +'<div class="row"><div class="stitle" style="margin:0">대본</div><button class="cpbtn" onclick="cp(document.getElementById(\'lf'+uid+'\').textContent,this)">전체복사</button></div>'
      +'<div class="sbox" id="lf'+uid+'">'+esc(v.longform||'')+'</div>'
      +(sf?'<div class="stitle">숏폼 '+(v.shortforms||[]).length+'개</div><div class="sfgrid">'+sf+'</div>':'')
      +'<div class="stitle">해시태그</div>'
      +'<div>'+((v.hashtags||[]).map(function(h){return '<span class="htag" onclick="cp(\''+esc(h)+'\',null)">'+esc(h)+'</span>'}).join(''))+'</div>'
      +mlh+sb(uid);
    document.getElementById(lid).replaceWith(card);
  }catch(e){err('yr',lid,'오류: '+e.message);}
  finally{btn.disabled=false;btn.textContent='🎬 스크립트 생성';}
}

async function genSH(){
  var btn=document.getElementById('sb');
  btn.disabled=true; btn.textContent='⏳ 생성 중...';
  var count=parseInt(document.getElementById('sn').value);
  var lid=ld('sr');
  var now=new Date().toLocaleTimeString('ko-KR',{hour:'2-digit',minute:'2-digit'});
  var uid=''+Date.now();
  try{
    var resp=await fetch('/api/shorts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({count:count})});
    var d=await resp.json();
    if(!d.success) throw new Error(d.error);
    var shorts=d.data.shorts||[];
    var items=shorts.map(function(s,i){
      var sid=uid+'_'+i;
      return '<div style="background:#0f0f1a;border:1px solid #2a2a3e;border-radius:7px;padding:11px;margin-bottom:7px">'
        +'<div style="display:flex;align-items:center;gap:7px;margin-bottom:7px">'
          +'<span style="background:#C9956C;color:#fff;border-radius:50%;width:18px;height:18px;display:inline-flex;align-items:center;justify-content:center;font-size:10px;font-weight:700">'+(s.id||i+1)+'</span>'
          +'<span class="bdg b1" style="font-size:9px">'+esc(s.category||'')+'</span>'
          +'<span style="font-size:12px;font-weight:600;color:#f3f4f6">'+esc(s.title||'')+'</span>'
        +'</div>'
        +(s.hook?'<div style="font-size:11px;color:#e879f9;margin-bottom:6px;padding:4px 7px;background:#c026d310;border-radius:5px">'+esc(s.hook)+'</div>':'')
        +'<span class="exbtn" onclick="var sc=this.nextElementSibling;sc.style.display=sc.style.display==\'none\'?\'block\':\'none\';this.textContent=sc.style.display==\'none\'?\'▶ 대본 보기\':\'▼ 접기\'">▶ 대본 보기</span>'
        +'<div class="exbox sbox">'+esc(s.script_30sec||'')+'</div>'
        +'<div style="margin-top:5px">'+((s.hashtags||[]).map(function(h){return '<span class="htag" onclick="cp(\''+esc(h)+'\',null)" style="font-size:9px">'+esc(h)+'</span>'}).join(''))+'</div>'
      +'</div>';
    }).join('');
    var card=document.createElement('div'); card.className='card';
    card.innerHTML='<div class="row" style="margin-bottom:10px"><div><span class="bdg b1">숏츠 '+shorts.length+'개</span><span style="font-size:10px;color:#4b5563;margin-left:5px">'+now+'</span></div><button class="cpbtn" onclick="this.closest(\'.card\').remove()">✕</button></div>'+items+sb(uid);
    document.getElementById(lid).replaceWith(card);
    btn.textContent='✅ 완료!'; setTimeout(function(){btn.textContent='⚡ 숏츠 생성'},2000);
  }catch(e){err('sr',lid,'오류: '+e.message);}
  finally{btn.disabled=false;}
}

async function genFC(){
  if(!fb64){alert('이미지를 먼저 업로드해주세요!');return;}
  var btn=document.getElementById('fb');
  btn.disabled=true; btn.textContent='⏳ 분석 중...';
  var lid=ld('fr');
  var now=new Date().toLocaleTimeString('ko-KR',{hour:'2-digit',minute:'2-digit'});
  var uid=''+Date.now();
  try{
    var resp=await fetch('/api/face',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image_base64:fb64,media_type:ftype,mode:document.getElementById('fm').value,person_name:document.getElementById('pn').value,concern_area:document.getElementById('ca').value})});
    var d=await resp.json();
    if(!d.success) throw new Error(d.error);
    var v=d.data; var rs=v.reels_script||{};
    var tl=Object.entries(rs).map(function(e){return '<div style="display:flex;gap:9px;margin-bottom:5px"><div style="font-size:11px;font-weight:700;color:#C9956C;min-width:50px">'+esc(e[0])+'</div><div style="font-size:11px;color:#d1d5db;line-height:1.8">'+esc(e[1])+'</div></div>'}).join('');
    var card=document.createElement('div'); card.className='card';
    card.innerHTML='<div class="row" style="margin-bottom:10px"><div><span class="bdg b1">'+esc(v.face_type||'분석완료')+'</span><span style="font-size:10px;color:#4b5563;margin-left:5px">'+now+'</span></div><button class="cpbtn" onclick="this.closest(\'.card\').remove()">✕</button></div>'
      +'<div style="display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-bottom:10px">'
        +'<div style="background:#0f0f1a;border:1px solid #2a2a3e;border-radius:7px;padding:10px"><div style="font-size:9px;font-weight:700;color:#C9956C;margin-bottom:4px">얼굴형</div><div style="font-size:13px;font-weight:700;margin-bottom:3px">'+esc(v.face_type||'')+'</div><div style="font-size:10px;color:#9ca3af">'+esc(v.face_features||'')+'</div></div>'
        +'<div style="background:#0f0f1a;border:1px solid #2a2a3e;border-radius:7px;padding:10px"><div style="font-size:9px;font-weight:700;color:#C9956C;margin-bottom:4px">장점</div><div style="font-size:11px;color:#d1d5db">'+esc(v.strength||'')+'</div></div>'
      +'</div>'
      +'<div class="stitle">30초 릴스 대본</div>'+tl
      +'<div class="row" style="margin-top:10px"><div class="stitle" style="margin:0">캡션</div><button class="cpbtn" onclick="cp(document.getElementById(\'cp'+uid+'\').textContent,this)">복사</button></div>'
      +'<div class="sbox" id="cp'+uid+'">'+esc(v.caption||'')+'</div>'
      +'<div>'+((v.hashtags||[]).map(function(h){return '<span class="htag" onclick="cp(\''+esc(h)+'\',null)">'+esc(h)+'</span>'}).join(''))+'</div>'
      +sb(uid);
    document.getElementById(lid).replaceWith(card);
  }catch(e){err('fr',lid,'오류: '+e.message);}
  finally{btn.disabled=false;btn.textContent='👤 분석 시작';}
}

async function genKW(){
  var kw=document.getElementById('ki').value.trim();
  if(!kw){alert('키워드를 입력해주세요!');return;}
  var btn=document.getElementById('kb');
  btn.disabled=true; btn.textContent='⏳ 추천 중...';
  var lid=ld('kr');
  var now=new Date().toLocaleTimeString('ko-KR',{hour:'2-digit',minute:'2-digit'});
  var uid=''+Date.now();
  try{
    var resp=await fetch('/api/keyword',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({keyword:kw,category:document.getElementById('kc').value})});
    var d=await resp.json();
    if(!d.success) throw new Error(d.error);
    var recs=d.data.recommendations||[];
    var items=recs.map(function(r,i){
      var rid=uid+'_'+i;
      return '<div style="background:#0f0f1a;border:1px solid #2a2a3e;border-radius:7px;padding:11px;margin-bottom:7px">'
        +'<div style="display:flex;align-items:center;gap:7px;margin-bottom:7px">'
          +'<span style="background:#C9956C;color:#fff;border-radius:50%;width:18px;height:18px;display:inline-flex;align-items:center;justify-content:center;font-size:10px;font-weight:700">'+(i+1)+'</span>'
          +'<span style="font-size:12px;font-weight:700;color:#f3f4f6">'+esc(r.title||'')+'</span>'
        +'</div>'
        +'<div style="font-size:11px;color:#e879f9;margin-bottom:6px;padding:4px 7px;background:#c026d310;border-radius:5px">'+esc(r.hook||'')+'</div>'
        +'<div style="font-size:11px;color:#9ca3af;margin-bottom:6px">'+((r.points||[]).map(function(p){return '• '+esc(p)}).join('<br>'))+'</div>'
        +'<span class="exbtn" onclick="var sc=this.nextElementSibling;sc.style.display=sc.style.display==\'none\'?\'block\':\'none\';this.textContent=sc.style.display==\'none\'?\'▶ 30초 대본 보기\':\'▼ 접기\'">▶ 30초 대본 보기</span>'
        +'<div class="exbox sbox">'+esc(r.script_30sec||'')+'</div>'
        +'<div style="margin-top:5px">'+((r.hashtags||[]).map(function(h){return '<span class="htag" onclick="cp(\''+esc(h)+'\',null)" style="font-size:9px">'+esc(h)+'</span>'}).join(''))+'</div>'
      +'</div>';
    }).join('');
    var card=document.createElement('div'); card.className='card';
    card.innerHTML='<div class="row" style="margin-bottom:10px"><div><span class="bdg b1">'+esc(kw)+'</span><span style="font-size:10px;color:#4b5563;margin-left:5px">'+recs.length+'개 · '+now+'</span></div><button class="cpbtn" onclick="this.closest(\'.card\').remove()">✕</button></div>'+items+sb(uid);
    document.getElementById(lid).replaceWith(card);
  }catch(e){err('kr',lid,'오류: '+e.message);}
  finally{btn.disabled=false;btn.textContent='🔑 주제 추천';}
}

async function loadHi(){
  var el=document.getElementById('hr');
  el.innerHTML='<div class="ld"><div class="spin"></div>로딩 중...</div>';
  try{
    var resp=await fetch('/api/history');
    var items=await resp.json();
    if(!items.length){el.innerHTML='<div class="empty"><div>📋</div><div>아직 생성된 콘텐츠가 없어요</div></div>';return;}
    var lbl={youtube:'🎬 유튜브',shorts_batch:'⚡ 숏츠',face:'👤 얼굴분석',keyword_reels:'🔑 키워드'};
    var h='<div class="card"><table class="tbl"><thead><tr><th>유형</th><th>내용</th><th>생성일시</th></tr></thead><tbody>';
    items.forEach(function(i){h+='<tr><td>'+(lbl[i.type]||i.type)+'</td><td>'+esc(i.preview||i.keyword||i.category||'-')+'</td><td style="color:#6b7280">'+(i.created_at||'')+'</td></tr>'});
    el.innerHTML=h+'</tbody></table></div>';
  }catch(e){el.innerHTML='<div class="err">오류: '+e.message+'</div>';}
}
</script>
</body>
</html>"""

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5100))
    print(f"POP 콘텐츠 AI: http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
