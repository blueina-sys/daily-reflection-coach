"""순수 데이터 로직: 시트 스키마 정의, 마이그레이션, 마음 날씨 점수 매핑.

Streamlit에 의존하지 않으므로 단위 테스트에서 바로 import할 수 있다.
"""

CURRENT_COLUMNS = [
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
    (V2_COLUMNS, None),
    (V1_COLUMNS, None),
    (LEGACY_COLUMNS, _legacy_transform),
]


# ---------- 오늘의 가이드 ----------
# 새 신호(예: 수면 데이터)를 추가하려면 이 테이블에 규칙 하나만 더하면 된다.
# applies: 신호 dict을 받아 해당 여부를 돌려주는 함수
# reason: 점수에 기여한 이유 문장을 만드는 함수
GUIDE_RULES = [
    {
        "id": "pilates_with_external",
        "score": 2,
        "applies": lambda s: s.get("pilates_with_external", False),
        "reason": lambda s: "어제 필라테스 후 외부 일정이 있었어요",
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
            score += rule["score"]
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
