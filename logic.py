"""순수 데이터 로직: 시트 스키마 정의, 마이그레이션, 마음 날씨 점수 매핑, KST 시간 계산.

Streamlit에 의존하지 않으므로 단위 테스트에서 바로 import할 수 있다.
"""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def now_kst(now: datetime | None = None) -> datetime:
    """현재 한국 시각. 배포 서버가 UTC여도 KST 기준으로 계산되도록 모든 시간은 여기서 얻는다.

    now에 aware datetime을 주면 그 시각을 KST로 변환한다(테스트용).
    """
    if now is None:
        now = datetime.now(timezone.utc)
    return now.astimezone(KST)


def today_kst(now: datetime | None = None) -> date:
    return now_kst(now).date()


def _medication_records(entries: list[tuple[date, str]]) -> dict:
    """(날짜, 값) 목록에서 O/X 기록만 골라 날짜별 dict으로 만든다."""
    records = {}
    for day, value in entries:
        value = str(value).strip().upper()
        if value in ("O", "X"):
            records[day] = value
    return records


def _medication_streak(records: dict, last_day: date) -> dict:
    """last_day(복용 O인 날)에서 거슬러 올라가며 연속 복용 구간을 찾는다.

    X를 만나면 중단하고, 기록 없는 날 하루는 연속으로 인정한다.
    """
    count = 0
    missing_streak = 0
    day = last_day
    start_day = last_day
    while True:
        value = records.get(day)
        if value == "O":
            count += 1
            missing_streak = 0
            start_day = day
        elif value == "X":
            break
        else:
            missing_streak += 1
            if missing_streak > 1:
                break
        day -= timedelta(days=1)
    return {"day_count": count, "start_date": start_day}


def medication_status(entries: list[tuple[date, str]]) -> dict:
    """일별 약 복용 O/X 기록만으로 현재 복용 상태를 계산한다.

    - 복용 중 여부: 가장 최근 O/X 기록이 O인지
    - N일째: 가장 최근 기록부터 거슬러 올라가며 연속된 O의 개수
    - start_date: 그 연속 구간의 첫 O가 기록된 날 (= 약 시작일 = 병원 방문일)
    entries의 순서는 무관하며 O/X 외의 값은 무시한다.
    """
    records = _medication_records(entries)
    if not records:
        return {"medicating": False, "day_count": 0, "start_date": None}

    latest = max(records)
    if records[latest] != "O":
        return {"medicating": False, "day_count": 0, "start_date": None}

    streak = _medication_streak(records, latest)
    return {"medicating": True, "day_count": streak["day_count"], "start_date": streak["start_date"]}


def episode_medication_start(records: dict, start: date, last_active: date) -> date | None:
    """회차 기간 안에서 처음 복용한 날을 찾아, 그 연속 구간의 시작일을 돌려준다.

    회차 전부터 복용 중이었다면 그 구간의 시작일(발생일 이전)이 나온다.
    """
    day = start
    while day <= last_active:
        if records.get(day) == "O":
            return _medication_streak(records, day)["start_date"]
        day += timedelta(days=1)
    return None

CURRENT_COLUMNS = [
    "날짜",
    "마음 날씨",
    "mood_score",
    "recovery_tag",
    "수면 점수",
    "수면_지속시간",
    "수면_취침시간",
    "수면_중단",
    "활력징후 이상",
    "활력징후 메모",
    "오늘 잘한 일",
    "감사한 일",
    "배운 점",
    "내일 가장 중요한 한 가지",
    "운동 종류",
    "운동 시간대",
    "운동 강도",
    "외부 일정 여부",
    "저녁 컨디션",
    "약 복용 여부",
    "복용 시작일",
    "증상_구내염",
    "증상_목아픔",
    "증상_피로감",
    "증상_기타명",
    "증상_기타정도",
    "입안 건조",
    "입안 따끔",
    "구강 자극",
    "구강 자극 종류",
    "구내염_병원방문일",
    "구내염_약시작일",
    "저장 시간",
]

# 구내염 추적 도입 이전
V4_COLUMNS = [
    "날짜",
    "마음 날씨",
    "mood_score",
    "recovery_tag",
    "수면 점수",
    "수면_지속시간",
    "수면_취침시간",
    "수면_중단",
    "활력징후 이상",
    "활력징후 메모",
    "오늘 잘한 일",
    "감사한 일",
    "배운 점",
    "내일 가장 중요한 한 가지",
    "운동 종류",
    "운동 시간대",
    "운동 강도",
    "외부 일정 여부",
    "저녁 컨디션",
    "약 복용 여부",
    "복용 시작일",
    "증상_구내염",
    "증상_목아픔",
    "증상_피로감",
    "증상_기타명",
    "증상_기타정도",
    "저장 시간",
]

# 몸 신호(수면/활력징후) 도입 이전
V3_COLUMNS = [
    "날짜",
    "마음 날씨",
    "mood_score",
    "recovery_tag",
    "오늘 잘한 일",
    "감사한 일",
    "배운 점",
    "내일 가장 중요한 한 가지",
    "운동 종류",
    "운동 시간대",
    "운동 강도",
    "외부 일정 여부",
    "저녁 컨디션",
    "약 복용 여부",
    "복용 시작일",
    "증상_구내염",
    "증상_목아픔",
    "증상_피로감",
    "증상_기타명",
    "증상_기타정도",
    "저장 시간",
]

# mood_score 도입 이전(운동/약 스키마)
V2_COLUMNS = [
    "날짜",
    "마음 날씨",
    "오늘 잘한 일",
    "감사한 일",
    "배운 점",
    "내일 가장 중요한 한 가지",
    "운동 종류",
    "운동 시간대",
    "운동 강도",
    "외부 일정 여부",
    "저녁 컨디션",
    "약 복용 여부",
    "복용 시작일",
    "증상_구내염",
    "증상_목아픔",
    "증상_피로감",
    "증상_기타명",
    "증상_기타정도",
    "저장 시간",
]

# 활동/회복 에너지 스키마
V1_COLUMNS = [
    "날짜",
    "활동 에너지",
    "회복 에너지",
    "마음 날씨",
    "오늘 잘한 일",
    "감사한 일",
    "배운 점",
    "내일 가장 중요한 한 가지",
    "균형 점수",
    "코칭 메시지",
    "저장 시간",
]

# 최초 스키마
LEGACY_COLUMNS = [
    "날짜",
    "활동 에너지",
    "회복 에너지",
    "마음 날씨",
    "마음에 남은 일",
    "나를 위해 한 일",
]

# 인바디: 체지방률(%) 컬럼은 과거 데이터 보존을 위해 남겨두고, 체지방량(kg)은 body_fat_mass에 저장
INBODY_CURRENT_COLUMNS = ["날짜", "체중", "골격근량", "체지방률", "body_fat_mass", "저장 시간"]
INBODY_V1_COLUMNS = ["날짜", "체중", "골격근량", "체지방률", "저장 시간"]

MOOD_OPTIONS = ["맑음", "구름 조금", "흐림", "비 온 뒤 갬", "가벼운 비", "폭우", "무지개"]
MOOD_SCORE = {
    "맑음": 3,
    "무지개": 3,
    "구름 조금": 2,
    "비 온 뒤 갬": 2,
    "흐림": 1,
    "가벼운 비": 1,
    "폭우": 0,
}
RECOVERY_MOODS = {"비 온 뒤 갬", "무지개"}
MOOD_EMOJI = {
    "맑음": "☀️",
    "구름 조금": "⛅",
    "흐림": "☁️",
    "비 온 뒤 갬": "🌦️",
    "가벼운 비": "🌧️",
    "폭우": "⛈️",
    "무지개": "🌈",
}


def mood_fields_for(mood: str) -> dict:
    """마음 날씨 값으로부터 저장용 mood_score / recovery_tag 값을 만든다."""
    mood = str(mood).strip()
    if mood not in MOOD_SCORE:
        return {"mood_score": "", "recovery_tag": ""}
    return {
        "mood_score": MOOD_SCORE[mood],
        "recovery_tag": "TRUE" if mood in RECOVERY_MOODS else "FALSE",
    }


def backfill_mood_fields(row: dict) -> dict:
    """마음 날씨가 있고 mood_score가 비어 있으면 소급해서 채운다."""
    if str(row.get("mood_score", "")).strip() == "":
        row.update(mood_fields_for(row.get("마음 날씨", "")))
    return row


def _legacy_transform(row: dict) -> dict:
    row["오늘 잘한 일"] = row.get("마음에 남은 일", "")
    row["배운 점"] = row.get("나를 위해 한 일", "")
    return row


_MIGRATIONS = [
    (V4_COLUMNS, None),
    (V3_COLUMNS, None),
    (V2_COLUMNS, None),
    (V1_COLUMNS, None),
    (LEGACY_COLUMNS, _legacy_transform),
]


# ---------- 수면 점수 ----------
# min 이상이면 해당 구간. label은 입력 화면 안내, phrase는 가이드 카드 이유 문구,
# score는 오늘의 가이드 점수. 기준을 바꾸려면 이 표만 고치면 된다.
SLEEP_TIERS = [
    {"min": 85, "label": "매우 좋음", "score": 0, "phrase": ""},
    {"min": 70, "label": "양호", "score": 1, "phrase": "조금 아쉬웠어요"},
    {"min": 50, "label": "부족", "score": 2, "phrase": "부족했어요"},
    {"min": 0, "label": "많이 부족", "score": 3, "phrase": "많이 부족했어요"},
]
SLEEP_LOW_THRESHOLD = 70


def sleep_tier(score) -> dict | None:
    """수면 점수가 속한 구간을 돌려준다. 값이 없거나 숫자가 아니면 None."""
    if score is None or score == "":
        return None
    try:
        value = float(score)
    except (TypeError, ValueError):
        return None
    for tier in SLEEP_TIERS:
        if value >= tier["min"]:
            return tier
    return None


def sleep_guide_score(score) -> int:
    tier = sleep_tier(score)
    return tier["score"] if tier else 0


# ---------- 오늘의 가이드 ----------
# 새 신호(예: 수면 데이터)를 추가하려면 이 테이블에 규칙 하나만 더하면 된다.
# applies: 신호 dict을 받아 해당 여부를 돌려주는 함수
# reason: 점수에 기여한 이유 문장을 만드는 함수
def _exercise_detail_suffix(signals: dict) -> str:
    parts = [p for p in (signals.get("exercise_time"), signals.get("exercise_intensity")) if p]
    return f" ({' · '.join(parts)})" if parts else ""


GUIDE_RULES = [
    {
        # score가 함수면 신호에 따라 점수가 달라진다 (수면 구간별 0~3점)
        "id": "sleep",
        "score": lambda s: sleep_guide_score(s.get("sleep_score")),
        "applies": lambda s: sleep_guide_score(s.get("sleep_score")) > 0,
        "reason": lambda s: (
            f"어젯밤 수면 점수가 {s['sleep_score']}점으로 {sleep_tier(s['sleep_score'])['phrase']}"
        ),
    },
    {
        "id": "vital_abnormal",
        "score": 3,
        "applies": lambda s: s.get("vital_abnormal", False),
        "reason": lambda s: "활력 징후 이상 알림이 있었어요",
    },
    {
        "id": "pilates_with_external",
        "score": 2,
        "applies": lambda s: s.get("pilates_with_external", False),
        "reason": lambda s: f"어제 필라테스 후 외부 일정이 있었어요{_exercise_detail_suffix(s)}",
    },
    {
        # 어제 필라테스 배지를 대체하는 정보성 불릿 (점수에는 영향 없음)
        "id": "pilates_info",
        "score": 0,
        "applies": lambda s: s.get("pilates", False) and not s.get("pilates_with_external", False),
        "reason": lambda s: f"어제 필라테스를 했어요{_exercise_detail_suffix(s)}",
    },
    {
        "id": "low_evening_condition",
        "score": 2,
        "applies": lambda s: s.get("evening_condition") is not None and s["evening_condition"] <= 2,
        "reason": lambda s: f"어제 저녁 컨디션이 {s['evening_condition']}점이었어요",
    },
    {
        "id": "severe_symptom",
        "score": 2,
        "applies": lambda s: bool(s.get("severe_symptoms")),
        "reason": lambda s: f"어제 {', '.join(s['severe_symptoms'])} 증상이 심했어요",
    },
    {
        "id": "moderate_symptom",
        "score": 1,
        "applies": lambda s: bool(s.get("moderate_symptoms")),
        "reason": lambda s: f"어제 {', '.join(s['moderate_symptoms'])} 증상이 가볍게 있었어요",
    },
    {
        "id": "medicating",
        "score": 1,
        "applies": lambda s: s.get("medicating", False),
        "reason": lambda s: (
            f"복용 {s['med_day_count']}일째예요" if s.get("med_day_count") else "약을 복용 중이에요"
        ),
    },
    {
        "id": "storm_mood",
        "score": 2,
        "applies": lambda s: s.get("mood_score") == 0,
        "reason": lambda s: "어제 마음 날씨가 폭우였어요",
    },
]

# (최소 점수, 이모지, 레벨 키, 헤드라인, 행동 제안) — 위에서부터 먼저 맞는 레벨 적용
GUIDE_LEVELS = [
    (4, "🔴", "red", "오늘은 회복이 우선이에요", "꼭 해야 할 일 하나만 정하고, 나머지는 내일로"),
    (2, "🟡", "yellow", "오늘은 페이스 조절이 필요해요", "오늘 일정 중 미룰 수 있는 건 하나 미뤄보세요"),
    (0, "🟢", "green", "평소대로 지내도 좋아요", "컨디션 좋은 날이에요. 그래도 저녁엔 여유를 남겨두세요"),
]


def evaluate_guide(signals: dict) -> dict:
    """신호 dict을 받아 점수·이유·신호등 레벨을 계산한다."""
    score = 0
    reasons = []
    for rule in GUIDE_RULES:
        if rule["applies"](signals):
            rule_score = rule["score"]
            score += rule_score(signals) if callable(rule_score) else rule_score
            reasons.append(rule["reason"](signals))

    for min_score, emoji, level, headline, suggestion in GUIDE_LEVELS:
        if score >= min_score:
            return {
                "score": score,
                "reasons": reasons,
                "emoji": emoji,
                "level": level,
                "headline": headline,
                "suggestion": suggestion,
            }
    raise AssertionError("GUIDE_LEVELS must cover score 0")


# ---------- 구내염 추적 ----------
ORAL_IRRITATION_TYPES = ["매운/짠", "뜨거운", "딱딱한/씹다 상처", "음주", "기타"]
ULCER_ACTIVE_LEVELS = ("보통", "심함")
ULCER_PATTERN_MIN_EPISODES = 3
ULCER_SIGNAL_WINDOW_DAYS = 3  # 발생일 직전 며칠을 신호 구간으로 볼지 (D-3 ~ D0)

# 🟡 주의 배너를 켜는 보조 신호 표. 신호를 더하거나 기준을 바꾸려면 여기만 고치면 된다.
ULCER_WARNING_TRIGGERS = [
    {
        "id": "low_mood",
        "label": "마음 날씨가 흐렸어요",
        "applies": lambda s: s.get("mood_score") is not None and s["mood_score"] <= 1,
    },
    {
        "id": "low_sleep",
        "label": f"수면 점수가 {SLEEP_LOW_THRESHOLD} 미만이었어요",
        "applies": lambda s: s.get("sleep_score") is not None and s["sleep_score"] < SLEEP_LOW_THRESHOLD,
    },
    {
        "id": "fatigue",
        "label": "피로감이 있었어요",
        "applies": lambda s: s.get("fatigue_level") in ULCER_ACTIVE_LEVELS,
    },
    {
        "id": "irritation",
        "label": "구강 자극이 있었어요",
        "applies": lambda s: bool(s.get("irritation")),
    },
]
ULCER_WARNING_ACTIONS = ["물 충분히 마시기", "맵고 짠 음식 피하기", "운동 강도 낮추기"]
WEEKEND_AHEAD_WEEKDAYS = (3, 4)  # 목(3), 금(4)


def mouth_ulcer_alert(signals: dict) -> dict | None:
    """구내염 전조/주의 배너 내용을 만든다. 조건에 걸리지 않으면 None(=배너 숨김)."""
    if signals.get("sting"):
        notes = []
        if signals.get("weekday") in WEEKEND_AHEAD_WEEKDAYS:
            notes.append("주말이 다가와요 — 병원 방문이나 약 시작을 미루지 마세요")
        return {
            "level": "red",
            "emoji": "🔴",
            "headline": "구내염 전조 가능성. 오늘 안에 대응하세요",
            "reasons": ["입안이 따끔·화끈했어요"],
            "notes": notes,
        }

    if signals.get("dry"):
        reasons = [rule["label"] for rule in ULCER_WARNING_TRIGGERS if rule["applies"](signals)]
        if reasons:
            return {
                "level": "yellow",
                "emoji": "🟡",
                "headline": "구내염 주의 신호",
                "reasons": ["입안이 건조·이물감이 있었어요"] + reasons,
                "notes": ULCER_WARNING_ACTIONS,
            }
    return None


def _parse_date(value) -> date | None:
    text = str(value).strip() if value is not None else ""
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def detect_ulcer_episodes(entries: list[dict]) -> list[dict]:
    """구내염 증상 기록에서 발생 회차를 자동으로 찾아낸다.

    entries: [{"date": date, "level": "없음/보통/심함", "medicated": "O/X", "hospital": "YYYY-MM-DD"}]
    '없음'에서 '보통 이상'으로 처음 바뀐 날이 발생일이고, 다시 '없음'이 되면 회복으로 본다.

    약 시작일은 복용 O/X 기록에서 자동으로 찾는다(회차 중 첫 복용 구간의 시작일).
    병원 방문일은 보통 약 시작일과 같으므로 그 값을 쓰고, hospital에 값이 있으면
    예외 상황으로 보고 그 날짜로 덮어쓴다.
    """
    rows = sorted((e for e in entries if e.get("date")), key=lambda e: e["date"])
    med_records = _medication_records([(row["date"], row.get("medicated", "")) for row in rows])

    episodes = []
    current = None
    for row in rows:
        active = str(row.get("level", "")).strip() in ULCER_ACTIVE_LEVELS
        if active:
            if current is None:
                current = {"start": row["date"], "last_active": row["date"], "hospital": None}
            else:
                current["last_active"] = row["date"]
            manual_hospital = _parse_date(row.get("hospital"))
            if manual_hospital:
                current["hospital"] = manual_hospital
        elif current is not None:
            episodes.append(current)
            current = None

    if current is not None:
        current["ongoing"] = True
        episodes.append(current)

    results = []
    for index, episode in enumerate(episodes):
        start = episode["start"]
        last_active = episode["last_active"]
        med_start = episode_medication_start(med_records, start, last_active)
        hospital = episode.get("hospital") or med_start
        results.append(
            {
                "start": start,
                "last_active": last_active,
                "ongoing": episode.get("ongoing", False),
                "duration_days": (last_active - start).days + 1,
                "med_start": med_start,
                "hospital": hospital,
                "hospital_is_manual": episode.get("hospital") is not None,
                "response_days": None if med_start is None else (med_start - start).days,
                "delay_days": None if hospital is None else (hospital - start).days,
                "gap_days": None if index == 0 else (start - episodes[index - 1]["start"]).days,
            }
        )
    return results


def ulcer_response_comparison(episodes: list[dict]) -> dict | None:
    """병원 방문이 빨랐던 회차와 늦은 회차의 평균 지속일수를 비교한다.

    비교할 회차가 부족하거나 한쪽 그룹이 비면 None(=표시하지 않음).
    """
    usable = [e for e in episodes if e.get("delay_days") is not None and not e.get("ongoing")]
    if len(usable) < 2:
        return None

    delays = sorted(e["delay_days"] for e in usable)
    middle = len(delays) // 2
    threshold = delays[middle] if len(delays) % 2 else (delays[middle - 1] + delays[middle]) / 2

    fast = [e for e in usable if e["delay_days"] <= threshold]
    slow = [e for e in usable if e["delay_days"] > threshold]
    if not fast or not slow:
        return None

    return {
        "threshold": threshold,
        "fast_count": len(fast),
        "slow_count": len(slow),
        "fast_avg_duration": sum(e["duration_days"] for e in fast) / len(fast),
        "slow_avg_duration": sum(e["duration_days"] for e in slow) / len(slow),
    }


SLEEP_EVENING_MIN_DAYS = 10


def sleep_evening_gap(pairs: list[tuple], min_days: int = SLEEP_EVENING_MIN_DAYS) -> float | None:
    """수면 점수가 낮았던 날의 저녁 컨디션이 평균 몇 점 낮았는지 계산한다.

    pairs: (수면 점수, 저녁 컨디션) 목록. 둘 다 있는 날만 센다.
    자료가 min_days 미만이거나 양쪽 그룹 중 하나가 비면 None(=표시하지 않음).
    """
    low, high = [], []
    for sleep, evening in pairs:
        if sleep is None or evening is None or sleep == "" or evening == "":
            continue
        try:
            sleep_value = float(sleep)
            evening_value = float(evening)
        except (TypeError, ValueError):
            continue
        (low if sleep_value < SLEEP_LOW_THRESHOLD else high).append(evening_value)

    if len(low) + len(high) < min_days or not low or not high:
        return None

    diff = sum(high) / len(high) - sum(low) / len(low)
    return diff if diff > 0 else None


def build_migrated_rows(values: list[list[str]]) -> list[list] | None:
    """구버전 스키마의 시트 전체 값을 현재 스키마로 변환한다.

    이미 현재 스키마이거나 알 수 없는 헤더면 None을 반환한다(행 변환 없음).
    """
    if not values:
        return None
    header = values[0]
    if header[: len(CURRENT_COLUMNS)] == CURRENT_COLUMNS:
        return None

    for schema, transform in _MIGRATIONS:
        if header[: len(schema)] != schema:
            continue
        migrated = [CURRENT_COLUMNS]
        for raw in values[1:]:
            padded = raw + [""] * (len(schema) - len(raw))
            row = dict(zip(schema, padded))
            if transform:
                transform(row)
            backfill_mood_fields(row)
            migrated.append([row.get(column, "") for column in CURRENT_COLUMNS])
        return migrated
    return None


def build_migrated_inbody_rows(values: list[list[str]]) -> list[list] | None:
    """구버전 인바디 시트를 현재 스키마로 변환한다. 변환할 것이 없으면 None."""
    if not values:
        return None
    header = values[0]
    if header[: len(INBODY_CURRENT_COLUMNS)] == INBODY_CURRENT_COLUMNS:
        return None
    if header[: len(INBODY_V1_COLUMNS)] != INBODY_V1_COLUMNS:
        return None

    migrated = [INBODY_CURRENT_COLUMNS]
    for raw in values[1:]:
        padded = raw + [""] * (len(INBODY_V1_COLUMNS) - len(raw))
        row = dict(zip(INBODY_V1_COLUMNS, padded))
        migrated.append([row.get(column, "") for column in INBODY_CURRENT_COLUMNS])
    return migrated
