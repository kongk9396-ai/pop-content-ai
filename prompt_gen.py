"""
팝성형외과 오늘의 추천 프롬프트 10개 자동 생성기
-- 역추적 방식 --
1. Perplexity로 경쟁사 노출 키워드 스캔
2. 경쟁사가 인용된 응답 분석
3. 그 응답을 만들 수 있었던 실제 환자 질문 역추출
4. 네이버 DataLab 실검과 교차해서 최종 10개 확정

실행: python prompt_gen.py [--force]
출력: output/prompts/YYYYMMDD.json
"""

import sys
import io
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8","utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import os, json, time, random, requests, urllib.request, urllib.parse
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv()

PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "")
ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
NAVER_CLIENT_ID    = os.environ.get("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET= os.environ.get("NAVER_CLIENT_SECRET", "")

claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

BASE_DIR   = Path(__file__).parent
PROMPT_DIR = BASE_DIR / "output" / "prompts"
PROMPT_DIR.mkdir(parents=True, exist_ok=True)

BRAND = "팝성형외과"
CATEGORY_LABEL = {"eye": "눈성형", "lifting": "리프팅", "nose": "코성형"}

# 경쟁사 탐색용 시드 키워드 (카테고리별)
SEED_QUERIES = {
    "eye": [
        "강남 쌍꺼풀 수술 잘하는 곳",
        "강남 눈매교정 추천 성형외과",
        "압구정 눈성형 잘하는 병원",
    ],
    "lifting": [
        "강남 안면거상 추천 성형외과",
        "강남 실리프팅 잘하는 곳",
        "압구정 이마거상 전문 병원",
    ],
    "nose": [
        "강남 코성형 잘하는 성형외과",
        "압구정 복코 교정 추천",
        "강남 코끝 성형 전문 병원",
    ],
}

# 카테고리별 생성 수
DAILY_PLAN = {"eye": 4, "lifting": 3, "nose": 3}


# -- Step 1: Perplexity로 경쟁사 노출 응답 수집 --

def ask_perplexity_simple(query: str) -> str:
    """Perplexity에 질문 -> 응답 텍스트 반환"""
    if not PERPLEXITY_API_KEY:
        return ""
    try:
        r = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers={"Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                     "Content-Type": "application/json"},
            json={"model": "sonar",
                  "messages": [
                      {"role": "system", "content":
                       "당신은 성형외과 정보를 제공하는 AI입니다. 구체적인 병원명을 포함해 답변하세요."},
                      {"role": "user", "content": query}
                  ],
                  "max_tokens": 600, "temperature": 0.1},
            timeout=25,
        )
        if r.status_code == 429:
            time.sleep(8)
            return ask_perplexity_simple(query)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"    [Perplexity 오류] {e}")
        return ""


# -- Step 2: 네이버 DataLab 실검 키워드 --

def get_naver_trending(category: str) -> list:
    if not NAVER_CLIENT_ID:
        return []
    seeds = SEED_QUERIES.get(category, [])[:2]
    collected = []
    for seed in seeds:
        try:
            q = urllib.parse.quote(seed)
            url = f"https://openapi.naver.com/v1/search/blog?query={q}&display=5&sort=date"
            req = urllib.request.Request(url)
            req.add_header("X-Naver-Client-Id", NAVER_CLIENT_ID)
            req.add_header("X-Naver-Client-Secret", NAVER_CLIENT_SECRET)
            res = urllib.request.urlopen(req, timeout=10)
            items = json.loads(res.read().decode("utf-8")).get("items", [])
            for item in items:
                title = item.get("title","").replace("<b>","").replace("</b>","")
                if title and len(title) <= 25:
                    collected.append(title)
        except Exception:
            pass
    return list(dict.fromkeys(collected))[:8]


# -- Step 3: 역추적 - Claude가 실제 환자 질문 추출 --

def reverse_engineer_prompts(
    category: str,
    competitor_responses: list,
    trending_keywords: list,
    count: int,
) -> list:
    """
    경쟁사 AI 응답을 보고 역추적:
    '이 응답을 만들어낸 환자의 실제 질문은 무엇이었을까?'
    -> 팝성형외과가 끼어들 수 있는 질문 형태로 변환
    """
    label = CATEGORY_LABEL[category]

    comp_text = "\n---\n".join(competitor_responses[:3]) if competitor_responses else "데이터 없음"
    trend_text = ", ".join(trending_keywords[:6]) if trending_keywords else "없음"

    prompt = f"""당신은 성형외과 AI 검색 전략 전문가입니다.

[팝성형외과 정보]
- 위치: 강남/압구정 (19년 역사)
- 주력: {label}
- 수술 실명제 운영, 자연스러운 결과 중심

[경쟁사 AI 응답 샘플 (Perplexity 실제 응답)]
{comp_text}

[네이버 실시간 검색 트렌드]
{trend_text}

[역추적 미션]
위 경쟁사 응답들을 분석해서:
1. 이 응답들을 만들어낸 실제 환자 질문 패턴을 역추적하세요
2. 팝성형외과가 그 질문에서 노출될 수 있도록 질문을 변형하세요
3. 실제 환자가 AI 검색창에 입력할 법한 자연스러운 구어체로 작성하세요

[조건]
- 총 {count}개
- 30~70자 사이의 자연스러운 구어체 (격식체 금지)
- 강남/압구정/서초 지역명 포함
- 나이대/증상/고민/비교 등 구체적 상황 포함
- 팝성형외과를 직접 언급하지 말 것 (검색 쿼리이므로)
- 아래 유형 섞어서: 지역 비교형 / 증상 고민형 / 나이대 타깃형 / 비교 선택형

JSON 배열로만 응답 (다른 텍스트 없이):
[
  {{
    "prompt": "실제 환자 질문",
    "type": "유형",
    "target_keyword": "핵심 타깃 키워드",
    "reverse_from": "역추적한 경쟁사 패턴 요약"
  }}
]"""

    try:
        r = claude.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = r.content[0].text.strip().replace("```json","").replace("```","").strip()
        return json.loads(raw)
    except Exception as e:
        print(f"    [Claude 역추적 오류] {e}")
        return []


# -- Step 4: fallback (API 없을 때) --

FALLBACK = {
    "eye": [
        {"prompt": "강남에서 눈 작은데 쌍수 자연스럽게 해주는 성형외과 몇 군데 비교해줘",
         "type": "지역 비교형", "target_keyword": "강남 쌍꺼풀 자연스럽게"},
        {"prompt": "30대 초반인데 눈매교정이랑 쌍수 같이 받으면 어떤 곳이 좋아? 압구정 쪽으로",
         "type": "나이대 타깃형", "target_keyword": "눈매교정 쌍수 동시"},
        {"prompt": "강남 눈밑지방재배치 다크서클 심한데 잘하는 성형외과 추천해줘",
         "type": "증상 고민형", "target_keyword": "눈밑지방재배치 다크서클"},
        {"prompt": "매몰이랑 절개 차이 설명해주고 강남에서 경험 많은 곳 알려줘",
         "type": "비교 선택형", "target_keyword": "매몰 절개 차이"},
    ],
    "lifting": [
        {"prompt": "50대 여성인데 이마 주름이랑 눈꺼풀 처짐 심해서 강남에서 이마거상 전문으로 하는 곳 추천해줘",
         "type": "나이대 타깃형", "target_keyword": "이마거상 전문"},
        {"prompt": "실리프팅이랑 안면거상 차이가 뭐야? 강남에서 잘하는 곳 비교해줘",
         "type": "비교 선택형", "target_keyword": "실리프팅 안면거상 차이"},
        {"prompt": "압구정이나 청담동 쪽에서 얼굴 처짐 리프팅 잘하는 성형외과 알려줘",
         "type": "지역 비교형", "target_keyword": "압구정 리프팅"},
    ],
    "nose": [
        {"prompt": "강남에서 복코 교정 자연스럽게 해주는 성형외과 몇 군데 추천해줘",
         "type": "지역 비교형", "target_keyword": "복코 교정 자연스럽게"},
        {"prompt": "코 보형물 비침이 걱정돼서 강남에서 재수술 경험 많은 곳 찾고 있어",
         "type": "증상 고민형", "target_keyword": "코 보형물 비침 재수술"},
        {"prompt": "압구정에서 코끝 성형이랑 콧대 같이 하려는데 잘하는 성형외과 추천해줘",
         "type": "조합 시술형", "target_keyword": "코끝 콧대 동시"},
    ],
}


# -- 메인 실행 --

def run(force: bool = False):
    date_str = datetime.now().strftime("%Y%m%d")
    out_file = PROMPT_DIR / f"{date_str}.json"

    print(f"\n{'='*55}")
    print(f"팝성형외과 오늘의 추천 프롬프트 생성기 (역추적 방식)")
    print(f"날짜: {date_str}")
    print(f"  Perplexity : {'[OK] 역추적 가능' if PERPLEXITY_API_KEY else '[없음] (fallback 사용)'}")
    print(f"  Naver API  : {'[OK] 실검 연동' if NAVER_CLIENT_ID else '[없음]'}")
    print(f"{'='*55}")

    if out_file.exists() and not force:
        print(f"\n오늘 이미 생성됨: {out_file}")
        d = json.loads(out_file.read_text(encoding="utf-8"))
        for p in d["prompts"]:
            cat = CATEGORY_LABEL.get(p.get("category",""), "")
            print(f"  [{cat}] {p['prompt']}")
        return d

    all_prompts = []
    pid = 1

    for category, count in DAILY_PLAN.items():
        label = CATEGORY_LABEL[category]
        print(f"\n[{label}] {count}개 역추적 시작")

        # 1. Perplexity로 경쟁사 응답 수집
        competitor_responses = []
        if PERPLEXITY_API_KEY:
            seeds = SEED_QUERIES[category]
            print(f"  Perplexity 경쟁사 응답 수집 중 ({len(seeds)}개 쿼리)...", end="", flush=True)
            for seed in seeds:
                resp = ask_perplexity_simple(seed)
                if resp:
                    competitor_responses.append(resp)
                time.sleep(1.5)
            print(f" {len(competitor_responses)}개 수집 완료")
        else:
            print(f"  Perplexity 없음 -> fallback 사용")

        # 2. 네이버 실검
        trending = []
        if NAVER_CLIENT_ID:
            print(f"  네이버 실검 수집 중...", end="", flush=True)
            trending = get_naver_trending(category)
            print(f" {len(trending)}개")

        # 3. 역추적 또는 fallback
        if competitor_responses:
            print(f"  Claude 역추적 중...", end="", flush=True)
            raw_prompts = reverse_engineer_prompts(
                category, competitor_responses, trending, count
            )
            print(f" {len(raw_prompts)}개 생성")
        else:
            raw_prompts = FALLBACK.get(category, [])[:count]

        # 4. 형식 통일 + pid 부여
        for i, p in enumerate(raw_prompts[:count]):
            all_prompts.append({
                "id":             pid,
                "category":       category,
                "type":           p.get("type", "역추적형"),
                "prompt":         p.get("prompt", ""),
                "target_keyword": p.get("target_keyword", ""),
                "reverse_from":   p.get("reverse_from", ""),
                "source":         "perplexity_reverse" if competitor_responses else "fallback",
            })
            print(f"    {pid}. {p.get('prompt','')[:55]}")
            pid += 1

    # 저장
    data = {
        "date":         date_str,
        "generated_at": datetime.now().isoformat(),
        "method":       "perplexity_reverse_engineering",
        "total":        len(all_prompts),
        "prompts":      all_prompts,
    }
    out_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'='*55}")
    print(f"완료! 총 {len(all_prompts)}개 저장 -> {out_file}")
    print(f"{'='*55}\n")
    return data


if __name__ == "__main__":
    import sys
    run(force="--force" in sys.argv)
