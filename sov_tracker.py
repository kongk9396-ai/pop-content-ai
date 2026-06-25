"""
팝성형외과 AI 노출 점유율(Share of Voice) 트래커
Perplexity + Gemini + ChatGPT 세 모델 모두 측정

실행: python sov_tracker.py [--force]
출력: output/sov/YYYYMMDD.json
"""

import sys
import io
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8","utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import os, re, json, time, requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv()

PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "")
OPENAI_API_KEY     = os.environ.get("OPENAI_API_KEY", "")
GEMINI_API_KEY     = os.environ.get("GEMINI_API_KEY", "")
ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")

claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

BASE_DIR   = Path(__file__).parent
SOV_DIR    = BASE_DIR / "output" / "sov"
PROMPT_DIR = BASE_DIR / "output" / "prompts"
SOV_DIR.mkdir(parents=True, exist_ok=True)

OUR_BRAND   = "팝성형외과"
OUR_ALIASES = ["팝성형외과", "팝ps", "popps", "팝 성형외과"]

COMPETITORS = [
    "꿈꾸는성형외과", "1mm성형외과", "시크릿성형외과",
    "강남서연성형외과", "베리굿성형외과", "아몬드성형외과",
    "빌리프성형외과", "강남언니", "바비톡", "JW성형외과",
    "BK성형외과", "이지함성형외과", "리쥬란",
]

CATEGORY_LABEL = {"eye": "눈성형", "lifting": "리프팅", "nose": "코성형"}

SYSTEM_MSG = "당신은 성형외과 정보를 제공하는 AI입니다. 구체적인 병원명을 포함해 답변하세요."


# -- 모델별 API 호출 --

def ask_perplexity(prompt: str) -> dict:
    if not PERPLEXITY_API_KEY:
        return {"text": "", "sources": [], "error": "PERPLEXITY_API_KEY 없음"}
    try:
        r = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers={"Authorization": f"Bearer {PERPLEXITY_API_KEY}", "Content-Type": "application/json"},
            json={"model": "sonar", "messages": [
                {"role": "system", "content": SYSTEM_MSG},
                {"role": "user",   "content": prompt}
            ], "max_tokens": 800, "temperature": 0.2, "return_citations": True},
            timeout=30,
        )
        if r.status_code == 429:
            time.sleep(10); return ask_perplexity(prompt)
        r.raise_for_status()
        d = r.json()
        return {
            "text": d["choices"][0]["message"]["content"],
            "sources": [c.get("url","") for c in d.get("citations", [])],
            "error": None,
        }
    except Exception as e:
        return {"text": "", "sources": [], "error": str(e)}


def ask_gemini(prompt: str) -> dict:
    if not GEMINI_API_KEY:
        return {"text": "", "sources": [], "error": "GEMINI_API_KEY 없음"}
    try:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": SYSTEM_MSG + "\n\n" + prompt}]}],
                  "generationConfig": {"maxOutputTokens": 800, "temperature": 0.2}},
            timeout=30,
        )
        r.raise_for_status()
        d = r.json()
        text = d["candidates"][0]["content"]["parts"][0]["text"]
        return {"text": text, "sources": [], "error": None}
    except Exception as e:
        return {"text": "", "sources": [], "error": str(e)}


def ask_chatgpt(prompt: str) -> dict:
    if not OPENAI_API_KEY:
        return {"text": "", "sources": [], "error": "OPENAI_API_KEY 없음"}
    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={"model": "gpt-4o-mini",
                  "messages": [
                      {"role": "system", "content": SYSTEM_MSG},
                      {"role": "user",   "content": prompt}
                  ], "max_tokens": 800, "temperature": 0.2},
            timeout=30,
        )
        r.raise_for_status()
        d = r.json()
        return {"text": d["choices"][0]["message"]["content"], "sources": [], "error": None}
    except Exception as e:
        return {"text": "", "sources": [], "error": str(e)}


MODELS = {
    "perplexity": {"fn": ask_perplexity, "label": "Perplexity"},
    "gemini":     {"fn": ask_gemini,     "label": "Gemini"},
    "chatgpt":    {"fn": ask_chatgpt,    "label": "ChatGPT"},
}


# -- 분석 헬퍼 --

def check_mention(text: str, brand: str) -> bool:
    t = text.lower()
    aliases = OUR_ALIASES if brand == OUR_BRAND else [brand]
    return any(a.lower() in t for a in aliases)


def extract_mentioned_brands(text: str, all_brands: list) -> list:
    t = text.lower()
    return [b for b in all_brands if b.lower() in t]


def extract_search_keywords(text: str) -> list:
    if not text:
        return []
    try:
        r = claude.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=150,
            messages=[{"role": "user", "content":
                f"아래 AI 응답을 보고 검색에 사용했을 핵심 검색어 3개를 쉼표로만 출력:\n{text[:400]}"}]
        )
        return [k.strip() for k in r.content[0].text.strip().split(",") if k.strip()][:3]
    except Exception:
        return []


# -- 오늘 프롬프트 로드 --

def load_today_prompts() -> list:
    f = PROMPT_DIR / f"{datetime.now().strftime('%Y%m%d')}.json"
    if not f.exists():
        print("  프롬프트 파일 없음 -> prompt_gen.py 먼저 실행하세요")
        return []
    return json.loads(f.read_text(encoding="utf-8")).get("prompts", [])


# -- 메인 측정 --

def measure_sov(prompts: list) -> dict:
    date_str   = datetime.now().strftime("%Y%m%d")
    all_brands = [OUR_BRAND] + COMPETITORS
    total      = len(prompts)

    # 모델별 초기화
    model_data = {mid: {
        "label":        m["label"],
        "our_mentions": 0,
        "brand_counts": {b: 0 for b in all_brands},
        "errors":       0,
        "results":      [],
    } for mid, m in MODELS.items()}

    ai_keywords: list = []

    print(f"\n  총 {total}개 프롬프트 x {len(MODELS)}개 모델 = {total*len(MODELS)}회 측정\n")

    def query_one(p, mid):
        """단일 (프롬프트 x 모델) 측정 단위"""
        key = (PERPLEXITY_API_KEY if mid == "perplexity"
               else GEMINI_API_KEY if mid == "gemini"
               else OPENAI_API_KEY)
        if not key:
            return mid, p, None
        resp = MODELS[mid]["fn"](p.get("prompt", ""))
        return mid, p, resp

    # 모든 (프롬프트 x 모델) 조합 병렬 처리
    tasks = [(p, mid) for p in prompts for mid in MODELS]
    workers = min(len(tasks), 6)
    print(f"  병렬 처리 시작 (workers={workers}, 총 {len(tasks)}건)\n")

    done = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(query_one, p, mid): (p, mid)
            for p, mid in tasks
        }
        for future in as_completed(future_map):
            p, mid = future_map[future]
            pt  = p.get("prompt", "")
            cat = p.get("category", "")
            done += 1
            try:
                result_mid, result_p, resp = future.result()
                if resp is None:
                    continue
                if resp["error"]:
                    print(f"  [{done}/{len(tasks)}] [{MODELS[mid]['label']}] 오류: {resp['error'][:40]}")
                    model_data[mid]["errors"] += 1
                    continue

                text      = resp["text"]
                our_hit   = check_mention(text, OUR_BRAND)
                mentioned = extract_mentioned_brands(text, all_brands)
                kws       = extract_search_keywords(text)

                if our_hit:
                    model_data[mid]["our_mentions"] += 1
                for b in mentioned:
                    model_data[mid]["brand_counts"][b] = model_data[mid]["brand_counts"].get(b, 0) + 1
                ai_keywords.extend(kws)

                model_data[mid]["results"].append({
                    "prompt_id": p.get("id"), "category": cat,
                    "prompt": pt, "our_mention": our_hit,
                    "mentioned_brands": mentioned,
                    "ai_searched_keywords": kws,
                    "response_preview": text[:150],
                    "sources": resp["sources"][:3],
                })

                status = "[OK]" if our_hit else "[-]"
                rivals = ", ".join(mentioned[:2]) if mentioned else "없음"
                print(f"  [{done}/{len(tasks)}] {MODELS[mid]['label']} | {pt[:28]} | {status} | {rivals}")

            except Exception as e:
                print(f"  [{done}/{len(tasks)}] 오류: {e}")
                model_data[mid]["errors"] += 1

    # -- 집계 --
    model_summary = {}
    for mid, d in model_data.items():
        measured = len(d["results"])
        sov = round(d["our_mentions"] / measured * 100, 1) if measured else 0.0
        ranking = sorted(
            [{"brand": b, "count": c, "pct": round(c / max(measured,1) * 100, 1)}
             for b, c in d["brand_counts"].items()],
            key=lambda x: x["count"], reverse=True
        )
        # 우리 병원 순위 -- 언급 없으면 None
        our_entry = next((r for r in ranking if r["brand"] == OUR_BRAND), None)
        if our_entry and our_entry["count"] > 0:
            our_rank = next((i+1 for i,r in enumerate(ranking) if r["brand"] == OUR_BRAND), None)
        else:
            our_rank = None
        model_summary[mid] = {
            "label": d["label"], "measured": measured,
            "our_mentions": d["our_mentions"], "sov_pct": sov,
            "our_rank": our_rank, "ranking": ranking[:10],
        }

    # 전체 통합 SOV
    total_measured = sum(d["measured"] for d in model_summary.values())
    total_ours     = sum(d["our_mentions"] for d in model_summary.values())
    overall_sov    = round(total_ours / total_measured * 100, 1) if total_measured else 0.0

    # AI 검색 키워드 빈도
    kw_count: dict = {}
    for kw in ai_keywords:
        kw_count[kw] = kw_count.get(kw, 0) + 1
    top_keywords = sorted(
        [{"keyword": k, "count": c} for k, c in kw_count.items()],
        key=lambda x: x["count"], reverse=True
    )[:10]

    # 통합 Industry Ranking
    combined: dict = {}
    for d in model_summary.values():
        for r in d["ranking"]:
            combined[r["brand"]] = combined.get(r["brand"], 0) + r["count"]
    industry_ranking = sorted(
        [{"brand": b, "total_count": c,
          "pct": round(c / max(total_measured,1) * 100, 1)}
         for b, c in combined.items()],
        key=lambda x: x["total_count"], reverse=True
    )

    # -- 갭 키워드 추출 (미언급 프롬프트에서 타깃 키워드 수집) --
    gap_keywords = []
    for mid, d in model_data.items():
        for r in d["results"]:
            if not r["our_mention"]:
                kw = r.get("ai_searched_keywords", [])
                cat = r.get("category", "")
                prompt = r.get("prompt", "")
                gap_keywords.append({
                    "keyword":  r.get("prompt", "")[:40],
                    "category": cat,
                    "missed_model": MODELS[mid]["label"],
                    "mentioned_instead": r.get("mentioned_brands", [])[:3],
                    "ai_keywords": kw,
                })

    # gaps.json 저장 (run.py / magazine_run.py 가 참조)
    gaps_file = SOV_DIR.parent / "gaps.json"
    gaps_data = {
        "date":     date_str,
        "updated":  datetime.now().isoformat(),
        "overall_sov_pct": overall_sov,
        "gaps": gap_keywords,
        "gap_ai_keywords": list({kw for g in gap_keywords for kw in g.get("ai_keywords", [])}),
    }
    gaps_file.write_text(json.dumps(gaps_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  갭 키워드 {len(gap_keywords)}개 저장 -> {gaps_file}")

    return {
        "date": date_str,
        "measured_at": datetime.now().isoformat(),
        "summary": {
            "total_prompts": total,
            "total_measured": total_measured,
            "overall_sov_pct": overall_sov,
            "overall_our_mentions": total_ours,
        },
        "models": model_summary,
        "industry_ranking": industry_ranking,
        "top_ai_keywords": top_keywords,
        "gaps": gap_keywords,
    }


# -- 히스토리 --

def load_history(days: int = 10) -> list:
    files = sorted(SOV_DIR.glob("*.json"), reverse=True)[:days]
    history = []
    for f in reversed(list(files)):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            row = {"date": d["date"], "overall_sov_pct": d["summary"]["overall_sov_pct"]}
            for mid, ms in d.get("models", {}).items():
                row[f"{mid}_sov"] = ms.get("sov_pct", 0)
            history.append(row)
        except Exception:
            continue
    return history


# -- 실행 --


# -- SOV 인사이트 보고서 생성 ----------------------------------------

def generate_sov_report(sov_data: dict) -> dict:
    """측정 결과를 Claude로 분석해서 인사이트 보고서 생성"""
    date_str = sov_data.get("date", "")
    s = sov_data.get("summary", {})
    models = sov_data.get("models", {})
    ranking = sov_data.get("industry_ranking", [])
    gaps = sov_data.get("gaps", [])
    top_kws = sov_data.get("top_ai_keywords", [])

    # 성공/실패 프롬프트 분류
    all_results = []
    for mid, md in models.items():
        for r in md.get("results", []):
            r["model"] = md["label"]
            all_results.append(r)

    success_prompts = [r for r in all_results if r.get("our_mention")]
    fail_prompts    = [r for r in all_results if not r.get("our_mention")]

    success_samples = [r["prompt"][:60] for r in success_prompts[:3]]
    fail_samples    = [r["prompt"][:60] for r in fail_prompts[:3]]

    # 경쟁사 랭킹 Top5
    top_competitors = [r["brand"] for r in ranking[:5] if r["brand"] != OUR_BRAND]

    # 최고 기회 갭 (미노출 중 리프팅 우선)
    best_gap = None
    for g in gaps:
        if g.get("category") == "lifting":
            best_gap = g
            break
    if not best_gap and gaps:
        best_gap = gaps[0]

    prompt_text = f"""당신은 성형외과 AI 검색 마케팅 전문가입니다.
아래 팝성형외과의 AI 노출 점유율(SOV) 측정 데이터를 분석해서
경영진에게 보고할 수 있는 인사이트 보고서를 작성하세요.

[측정 데이터]
- 날짜: {date_str}
- 전체 SOV: {s.get('overall_sov_pct', 0)}% (프롬프트 {s.get('total_prompts',0)}개 측정)
- 모델별:
  Perplexity: {models.get('perplexity',{}).get('sov_pct',0)}% (#{models.get('perplexity',{}).get('our_rank','미언급')}위)
  Gemini:     {models.get('gemini',{}).get('sov_pct',0)}% (#{models.get('gemini',{}).get('our_rank','미언급')}위)
  ChatGPT:    {models.get('chatgpt',{}).get('sov_pct',0)}% (#{models.get('chatgpt',{}).get('our_rank','미언급')}위)
- 경쟁사 Top5: {', '.join(top_competitors)}
- 노출된 프롬프트 예시: {success_samples}
- 미노출 프롬프트 예시: {fail_samples}
- AI 검색 키워드: {[k['keyword'] for k in top_kws[:5]]}
- 최고 기회 갭: {best_gap.get('keyword','') if best_gap else '없음'}

[보고서 형식 - JSON으로만 응답]
{{
  "overall_summary": "전체 SOV 현황 2-3문장 요약",
  "strength_pattern": "노출 성공 패턴 분석 (어떤 질문에서 강점인지)",
  "weakness_pattern": "미노출 패턴 분석 (어떤 질문에서 약점인지)",
  "golden_prompt": "가장 빠르게 SOV 올릴 수 있는 추천 프롬프트 1개",
  "golden_prompt_reason": "이 프롬프트를 추천하는 이유",
  "content_strategy": "오늘 당장 작성해야 할 콘텐츠 전략 가이드 (구체적으로)",
  "next_step": "다음 액션 아이템 1가지",
  "summary_text": "📊 AI 검색 점유율(SoV) 진단 결과\\n\\n전체 점유율: {sov_pct}%\\n모델별: Perplexity {perp}% / Gemini {gem}% / ChatGPT {gpt}%\\n\\n[강점]\\n[보완점]\\n[오늘의 추천 프롬프트]"
}}"""

    try:
        r = claude.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt_text}]
        )
        raw = r.content[0].text.strip().replace("```json","").replace("```","").strip()
        report = json.loads(raw)
    except Exception as e:
        # fallback 보고서
        pct = s.get('overall_sov_pct', 0)
        report = {
            "overall_summary": f"전체 SOV {pct}%, Perplexity {models.get('perplexity',{}).get('sov_pct',0)}% / Gemini {models.get('gemini',{}).get('sov_pct',0)}% / ChatGPT {models.get('chatgpt',{}).get('sov_pct',0)}%",
            "strength_pattern": f"노출 프롬프트: {', '.join(success_samples[:2])}",
            "weakness_pattern": f"미노출 프롬프트: {', '.join(fail_samples[:2])}",
            "golden_prompt": best_gap.get("keyword","") if best_gap else "",
            "golden_prompt_reason": "미노출 갭 키워드",
            "content_strategy": "갭 키워드 기반 비교 칼럼 작성",
            "next_step": "golden_prompt 기반 블로그 글 1편 발행",
            "summary_text": f"SOV {pct}% | 분석 오류: {str(e)[:100]}",
            "error": str(e),
        }

    report["date"] = date_str
    report["generated_at"] = datetime.now().isoformat()
    return report


def run(force: bool = False):
    date_str = datetime.now().strftime("%Y%m%d")
    out_file = SOV_DIR / f"{date_str}.json"

    print(f"\n{'='*55}")
    print(f"팝성형외과 AI 노출 점유율 측정기 (3-Model)")
    print(f"날짜: {date_str}")
    print(f"  Perplexity : {'[OK]' if PERPLEXITY_API_KEY else '[X] 키 없음'}")
    print(f"  Gemini     : {'[OK]' if GEMINI_API_KEY     else '[X] 키 없음'}")
    print(f"  ChatGPT    : {'[OK]' if OPENAI_API_KEY     else '[X] 키 없음'}")
    print(f"{'='*55}")

    available = []
    if PERPLEXITY_API_KEY: available.append("Perplexity")
    if GEMINI_API_KEY: available.append("Gemini")
    if OPENAI_API_KEY: available.append("ChatGPT")

    if not available:
        print("\n.env에 API 키를 1개 이상 추가하세요.")
        print("Gemini는 무료: https://aistudio.google.com/app/apikey")
        return

    print(f"  사용 가능한 모델: {', '.join(available)}")

    if out_file.exists() and not force:
        print(f"\n오늘 이미 측정됨: {out_file}")
        d = json.loads(out_file.read_text(encoding="utf-8"))
        s = d["summary"]
        print(f"전체 SOV: {s['overall_sov_pct']}%")
        for mid, ms in d["models"].items():
            print(f"  {ms['label']}: {ms['sov_pct']}% (#{ms.get('our_rank','?')}위)")
        return d

    prompts = load_today_prompts()
    if not prompts:
        return

    data = measure_sov(prompts)
    out_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    s = data["summary"]
    print(f"\n{'='*55}")
    print(f"측정 완료! 전체 SOV: {s['overall_sov_pct']}%")
    for mid, ms in data["models"].items():
        rank = f"#{ms['our_rank']}위" if ms.get("our_rank") else "미언급"
        print(f"  {ms['label']}: {ms['sov_pct']}%  {rank}")
    print(f"\nIndustry Ranking Top 5:")
    for i, r in enumerate(data["industry_ranking"][:5], 1):
        marker = " <- 우리" if r["brand"] == OUR_BRAND else ""
        print(f"  {i}. {r['brand']} {r['pct']}%{marker}")
    print(f"\nAI 검색 키워드 Top 5:")
    for k in data["top_ai_keywords"][:5]:
        print(f"  {k['keyword']} ({k['count']}회)")
    print(f"\n저장: {out_file}")

    # SOV 인사이트 보고서 자동 생성
    print("\nSOV 보고서 생성 중...")
    report = generate_sov_report(data)
    report_file = SOV_DIR / f"{date_str}_report.json"
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"보고서 저장: {report_file}")
    print(f"\n--- SOV 보고서 미리보기 ---")
    print(report.get("summary_text", "")[:300])
    print(f"{'='*55}\n")
    data["report"] = report
    return data


if __name__ == "__main__":
    import sys
    run(force="--force" in sys.argv)
