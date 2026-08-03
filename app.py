import html
from datetime import datetime, time, timedelta

import gspread
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from google.oauth2.service_account import Credentials
from gspread.utils import rowcol_to_a1

from logic import (
    CURRENT_COLUMNS as COLUMNS,
    INBODY_CURRENT_COLUMNS as INBODY_COLUMNS,
    MOOD_EMOJI,
    MOOD_OPTIONS,
    SLEEP_LOW_THRESHOLD,
    SLEEP_TIERS,
    build_migrated_inbody_rows,
    build_migrated_rows,
    evaluate_guide,
    medication_status,
    mood_fields_for,
    now_kst,
    sleep_evening_gap,
    today_kst,
)


APP_TITLE = "오늘의 나"
WORKSHEET_DEFAULT = "records"
INBODY_WORKSHEET_DEFAULT = "inbody"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
MOOD_DESCRIPTIONS = {
    "맑음": "가볍고 여유 있음",
    "구름 조금": "무난한 하루",
    "흐림": "이유 없이 가라앉음",
    "비 온 뒤 갬": "나아지는 중",
    "가벼운 비": "걱정이 맴돎",
    "폭우": "버거운 하루",
    "무지개": "힘들었지만 기쁨 발견",
}

EXERCISE_TYPES = ["필라테스", "걷기", "기타", "안 함"]
INTENSITY_OPTIONS = ["가볍게", "보통", "힘듦"]
EXTERNAL_SCHEDULE_OPTIONS = ["있음", "없음"]
SYMPTOM_TYPES = ["구내염", "목 아픔", "피로감", "기타"]
SYMPTOM_COLUMN_MAP = {
    "구내염": "증상_구내염",
    "목 아픔": "증상_목아픔",
    "피로감": "증상_피로감",
    "기타": "증상_기타정도",
}
SYMPTOM_LEVELS = ["없음", "보통", "심함"]
DEFAULT_PILATES_TIME = time(10, 0)
DEFAULT_EXERCISE_TIME = time(9, 0)
PILATES_STAT_MIN_COUNT = 5
SYMPTOM_PATTERN_MIN_COUNT = 5
SYMPTOM_MOOD_DIFF_THRESHOLD = 0.8
MEDICATION_PATTERN_MIN_DAYS = 5
MEDICATION_MOOD_DIFF_THRESHOLD = 0.5


st.set_page_config(page_title=APP_TITLE, page_icon="🌱", layout="wide")

st.markdown(
    """
    <style>
    .stApp {
        background: #f7f9f7;
    }
    .block-container {
        max-width: 1080px;
        padding-top: 1.4rem;
        padding-bottom: 2.5rem;
    }
    h1 {
        color: #263c36;
        font-size: clamp(2rem, 6vw, 3.2rem);
        line-height: 1.05;
        white-space: nowrap;
    }
    h2, h3 {
        color: #263c36;
    }
    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #dfe8e3;
        border-radius: 8px;
        padding: 14px;
    }
    .small-note {
        color: #66736d;
        font-size: 0.86rem;
        margin-top: -0.25rem;
    }
    .guide-box {
        background: #ffffff;
        border: 1px solid #dfe8e3;
        border-radius: 8px;
        padding: 12px 14px;
        color: #40504a;
        line-height: 1.7;
        font-size: 0.94rem;
    }
    .coach-card {
        background: #ffffff;
        border: 1px solid #cfe2d8;
        border-left: 6px solid #4c8a72;
        border-radius: 8px;
        padding: 18px 20px;
        color: #263c36;
        line-height: 1.65;
        margin-top: 0.4rem;
    }
    .summary-card {
        background: #ffffff;
        border: 1px solid #dfe8e3;
        border-radius: 8px;
        padding: 14px 16px;
    }
    .guide-card {
        border-radius: 10px;
        padding: 16px 18px;
        margin-bottom: 0.8rem;
        line-height: 1.6;
        color: #263c36;
    }
    .guide-card-green {
        background: #e7f3ec;
        border: 1px solid #bcd9c8;
    }
    .guide-card-yellow {
        background: #fbf4e2;
        border: 1px solid #e8d9ab;
    }
    .guide-card-red {
        background: #faeae7;
        border: 1px solid #e8c3ba;
    }
    .guide-card-empty {
        background: #ffffff;
        border: 1px solid #dfe8e3;
        color: #66736d;
    }
    .guide-card-label {
        font-size: 0.8rem;
        letter-spacing: 0.04em;
        color: #66736d;
        margin-bottom: 2px;
    }
    .guide-card-headline {
        font-weight: 700;
        font-size: 1.08rem;
        margin-bottom: 4px;
    }
    .guide-card-reasons {
        margin: 6px 0;
        padding-left: 1.2rem;
    }
    .guide-card-reasons li {
        margin: 2px 0;
    }
    .guide-card-suggestion {
        margin-top: 6px;
        font-size: 0.92rem;
        color: #40504a;
    }
    .inbody-mini-title {
        font-weight: 600;
        color: #263c36;
        margin-bottom: 2px;
    }
    div[class*="st-key-mood_grid"] {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 10px;
    }
    [class*="st-key-mood_btn_"] button {
        height: auto;
        min-height: 64px;
        padding: 10px 8px;
        border-radius: 8px;
    }
    [class*="st-key-mood_btn_"] button p {
        margin: 0;
        line-height: 1.35;
    }
    [class*="st-key-mood_btn_"] button p:first-child {
        font-weight: 600;
    }
    [class*="st-key-mood_btn_"] button p:last-child {
        font-size: 0.78rem;
        opacity: 0.78;
    }
    [class*="st-key-mood_btn_"] button[kind="secondary"] {
        background: #ffffff;
        border: 1px solid #dfe8e3;
        color: #40504a;
    }
    @media (max-width: 640px) {
        .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
        }
        h1 {
            font-size: 2.15rem;
        }
        div[data-testid="stMetric"] {
            padding: 10px;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------- Google Sheets data layer ----------
def has_google_sheet_settings() -> bool:
    return "spreadsheet_id" in st.secrets and "gcp_service_account" in st.secrets


def _get_gspread_client():
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=SCOPES,
    )
    return gspread.authorize(creds)


def _last_column_letter(column_count: int) -> str:
    return rowcol_to_a1(1, column_count).rstrip("0123456789")


@st.cache_resource
def get_worksheet():
    client = _get_gspread_client()
    spreadsheet = client.open_by_key(st.secrets["spreadsheet_id"])
    worksheet_name = st.secrets.get("worksheet_name", WORKSHEET_DEFAULT)

    try:
        worksheet = spreadsheet.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows=1000, cols=len(COLUMNS))

    ensure_sheet_schema(worksheet)
    return worksheet


@st.cache_resource
def get_inbody_worksheet():
    client = _get_gspread_client()
    spreadsheet = client.open_by_key(st.secrets["spreadsheet_id"])
    worksheet_name = st.secrets.get("inbody_worksheet_name", INBODY_WORKSHEET_DEFAULT)

    try:
        worksheet = spreadsheet.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows=1000, cols=len(INBODY_COLUMNS))

    ensure_inbody_schema(worksheet)
    return worksheet


def ensure_sheet_schema(worksheet) -> None:
    values = worksheet.get_all_values()
    last_col = _last_column_letter(len(COLUMNS))

    if not values:
        worksheet.update(f"A1:{last_col}1", [COLUMNS])
        return

    migrated_rows = build_migrated_rows(values)
    if migrated_rows is None:
        if values[0][: len(COLUMNS)] != COLUMNS:
            worksheet.update(f"A1:{last_col}1", [COLUMNS])
        return

    worksheet.clear()
    worksheet.update(f"A1:{last_col}{len(migrated_rows)}", migrated_rows)


def ensure_inbody_schema(worksheet) -> None:
    values = worksheet.get_all_values()
    last_col = _last_column_letter(len(INBODY_COLUMNS))

    if not values:
        worksheet.update(f"A1:{last_col}1", [INBODY_COLUMNS])
        return

    migrated_rows = build_migrated_inbody_rows(values)
    if migrated_rows is None:
        if values[0][: len(INBODY_COLUMNS)] != INBODY_COLUMNS:
            worksheet.update(f"A1:{last_col}1", [INBODY_COLUMNS])
        return

    worksheet.clear()
    worksheet.update(f"A1:{last_col}{len(migrated_rows)}", migrated_rows)


@st.cache_data(ttl=60, show_spinner=False)
def load_reflections() -> pd.DataFrame:
    worksheet = get_worksheet()
    rows = worksheet.get_all_records(expected_headers=COLUMNS)
    df = pd.DataFrame(rows, columns=COLUMNS)
    if df.empty:
        return df

    df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
    df = df.dropna(subset=["날짜"])
    df["저녁 컨디션"] = pd.to_numeric(df["저녁 컨디션"], errors="coerce").astype("Int64")
    df["mood_score"] = pd.to_numeric(df["mood_score"], errors="coerce").astype("Int64")
    df["recovery_tag"] = df["recovery_tag"].astype(str).str.strip().str.upper().eq("TRUE")
    # 몸 신호 — 과거 기록에는 값이 없어 비어 있을 수 있다(Int64로 결측 허용)
    for column in ["수면 점수", "수면_지속시간", "수면_취침시간", "수면_중단"]:
        df[column] = pd.to_numeric(df[column], errors="coerce").astype("Int64")
    df["활력징후 이상"] = df["활력징후 이상"].astype(str).str.strip().str.upper().eq("O")
    return df.sort_values("날짜")


def save_reflection(record: dict) -> str:
    worksheet = get_worksheet()
    # 업서트 대상 행을 정확히 찾도록 캐시를 비우고 최신 데이터를 읽는다
    load_reflections.clear()
    df = load_reflections()
    values = [record[column] for column in COLUMNS]
    record_date = record["날짜"]
    last_col = _last_column_letter(len(COLUMNS))

    if not df.empty and record_date in df["날짜"].dt.strftime("%Y-%m-%d").values:
        row_index = df.index[df["날짜"].dt.strftime("%Y-%m-%d") == record_date][0] + 2
        worksheet.update(f"A{row_index}:{last_col}{row_index}", [values])
        load_reflections.clear()
        return "오늘 기록을 수정했습니다."

    worksheet.append_row(values, value_input_option="USER_ENTERED")
    load_reflections.clear()
    return "새로운 기록을 저장했습니다."


@st.cache_data(ttl=60, show_spinner=False)
def load_inbody() -> pd.DataFrame:
    worksheet = get_inbody_worksheet()
    rows = worksheet.get_all_records(expected_headers=INBODY_COLUMNS)
    df = pd.DataFrame(rows, columns=INBODY_COLUMNS)
    if df.empty:
        return df

    df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
    df = df.dropna(subset=["날짜"])
    for column in ["체중", "골격근량", "체지방률", "body_fat_mass"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df.sort_values("날짜")


def save_inbody(record: dict) -> str:
    worksheet = get_inbody_worksheet()
    load_inbody.clear()
    df = load_inbody()
    values = [record[column] for column in INBODY_COLUMNS]
    record_date = record["날짜"]
    last_col = _last_column_letter(len(INBODY_COLUMNS))

    if not df.empty and record_date in df["날짜"].dt.strftime("%Y-%m-%d").values:
        row_index = df.index[df["날짜"].dt.strftime("%Y-%m-%d") == record_date][0] + 2
        worksheet.update(f"A{row_index}:{last_col}{row_index}", [values])
        load_inbody.clear()
        return "인바디 기록을 수정했습니다."

    worksheet.append_row(values, value_input_option="USER_ENTERED")
    load_inbody.clear()
    return "인바디 기록을 저장했습니다."


# ---------- Analysis helpers ----------
def to_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_streak_days(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    recorded_dates = set(df["날짜"].dt.date)
    current_day = today_kst()
    streak = 0
    while current_day in recorded_dates:
        streak += 1
        current_day -= timedelta(days=1)
    return streak


def get_recent_records(df: pd.DataFrame, limit: int = 7) -> pd.DataFrame:
    if df.empty:
        return df
    return df.sort_values("날짜").tail(limit)


def recent_days(df: pd.DataFrame, days: int) -> pd.DataFrame:
    return get_recent_records(df, days)


def get_medication_status(df: pd.DataFrame) -> dict:
    """일별 O/X 기록으로 현재 복용 상태를 계산한다. (복용 시작일 컬럼은 더 이상 쓰지 않음)"""
    if df.empty:
        return {"medicating": False, "day_count": 0}
    entries = list(zip(df["날짜"].dt.date, df["약 복용 여부"].astype(str)))
    return medication_status(entries)


def calc_pilates_external_stat(df: pd.DataFrame) -> str | None:
    if df.empty or "저녁 컨디션" not in df:
        return None
    subset = df[(df["운동 종류"] == "필라테스") & (df["외부 일정 여부"] == "있음")]
    if len(subset) < PILATES_STAT_MIN_COUNT:
        return None
    overall_avg = df["저녁 컨디션"].mean()
    subset_avg = subset["저녁 컨디션"].mean()
    diff = overall_avg - subset_avg
    if pd.isna(diff) or diff <= 0:
        return None
    return f"필라테스 후 외부 일정이 있던 날 저녁 컨디션 평균이 {diff:.1f}점 낮았어요"


def calc_symptom_mood_patterns(df: pd.DataFrame) -> list[str]:
    """'심함' 증상 기록이 충분히 쌓인 증상 중, 그날 mood_score가 유의미하게 낮은 것을 찾는다."""
    messages = []
    if df.empty or "mood_score" not in df:
        return messages
    overall_avg = df["mood_score"].mean()
    if pd.isna(overall_avg):
        return messages

    for symptom in ("구내염", "목 아픔", "피로감"):
        column = SYMPTOM_COLUMN_MAP[symptom]
        severe = df[df[column] == "심함"]
        if len(severe) < SYMPTOM_PATTERN_MIN_COUNT:
            continue
        severe_avg = severe["mood_score"].mean()
        if pd.isna(severe_avg):
            continue
        if overall_avg - severe_avg >= SYMPTOM_MOOD_DIFF_THRESHOLD:
            messages.append(f"{symptom} 증상이 심했던 날은 마음 날씨도 흐린 편이었어요")
    return messages


def calc_medication_mood_pattern(df: pd.DataFrame) -> str | None:
    if df.empty or "mood_score" not in df:
        return None
    medicated = df[df["약 복용 여부"] == "O"]
    unmedicated = df[df["약 복용 여부"] == "X"]
    if len(medicated) < MEDICATION_PATTERN_MIN_DAYS:
        return None
    medicated_avg = medicated["mood_score"].mean()
    unmedicated_avg = unmedicated["mood_score"].mean()
    if pd.isna(medicated_avg) or pd.isna(unmedicated_avg):
        return None
    diff = medicated_avg - unmedicated_avg
    if abs(diff) < MEDICATION_MOOD_DIFF_THRESHOLD:
        return None
    if diff > 0:
        return f"약 복용 기간에는 마음 날씨가 더 맑은 편이었어요 (평균 +{diff:.1f}점)"
    return f"약 복용 기간에는 마음 날씨가 더 흐린 편이었어요 (평균 {diff:.1f}점)"


def calc_sleep_evening_pattern(df: pd.DataFrame) -> str | None:
    if df.empty or "수면 점수" not in df:
        return None
    pairs = [
        (None if pd.isna(sleep) else int(sleep), None if pd.isna(evening) else int(evening))
        for sleep, evening in zip(df["수면 점수"], df["저녁 컨디션"])
    ]
    diff = sleep_evening_gap(pairs)
    if diff is None:
        return None
    return f"수면 점수 {SLEEP_LOW_THRESHOLD} 미만인 날은 저녁 컨디션이 평균 {diff:.1f}점 낮았어요"


def build_guide_signals(df: pd.DataFrame) -> dict | None:
    """어제 기록에서 오늘의 가이드 점수 계산에 쓸 신호들을 모은다. 어제 기록이 없으면 None."""
    if df.empty:
        return None
    yesterday = today_kst() - timedelta(days=1)
    matches = df[df["날짜"].dt.date == yesterday]
    if matches.empty:
        return None
    record = matches.iloc[-1]

    severe_symptoms = []
    moderate_symptoms = []
    for symptom in SYMPTOM_TYPES:
        level = record.get(SYMPTOM_COLUMN_MAP[symptom])
        name = symptom if symptom != "기타" else (str(record.get("증상_기타명", "")).strip() or "기타")
        if level == "심함":
            severe_symptoms.append(name)
        elif level == "보통":
            moderate_symptoms.append(name)

    evening = record["저녁 컨디션"]
    mood_score = record["mood_score"]
    sleep_score = record["수면 점수"]
    med_status = get_medication_status(df)
    return {
        "sleep_score": None if pd.isna(sleep_score) else int(sleep_score),
        "vital_abnormal": bool(record["활력징후 이상"]),
        "pilates": record["운동 종류"] == "필라테스",
        "pilates_with_external": record["운동 종류"] == "필라테스" and record["외부 일정 여부"] == "있음",
        "exercise_time": str(record.get("운동 시간대", "")).strip(),
        "exercise_intensity": str(record.get("운동 강도", "")).strip(),
        "evening_condition": None if pd.isna(evening) else int(evening),
        "severe_symptoms": severe_symptoms,
        "moderate_symptoms": moderate_symptoms,
        "medicating": med_status["medicating"],
        "med_day_count": med_status["day_count"],
        "mood_score": None if pd.isna(mood_score) else int(mood_score),
    }


def had_recovery_yesterday(df: pd.DataFrame) -> bool:
    if df.empty or "recovery_tag" not in df:
        return False
    yesterday = today_kst() - timedelta(days=1)
    matches = df[df["날짜"].dt.date == yesterday]
    return bool(matches["recovery_tag"].any()) if not matches.empty else False


def calc_inbody_delta(df: pd.DataFrame) -> dict:
    """컬럼별로 값이 있는 최근 두 기록의 (최근값, 증감)을 돌려준다."""
    deltas = {}
    if df.empty:
        return deltas
    for column in ("체중", "골격근량", "body_fat_mass"):
        series = df[column].dropna()
        if series.empty:
            continue
        latest = float(series.iloc[-1])
        diff = float(series.iloc[-1] - series.iloc[-2]) if len(series) >= 2 else None
        deltas[column] = {"latest": latest, "diff": diff}
    return deltas


# ---------- UI rendering helpers ----------
def render_today_guide(df: pd.DataFrame) -> None:
    signals = build_guide_signals(df)
    if signals is None:
        st.markdown(
            "<div class='guide-card guide-card-empty'>"
            "<div class='guide-card-label'>오늘의 가이드</div>"
            "어제 기록을 저장하면 오늘의 가이드를 알려드려요"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    result = evaluate_guide(signals)
    reasons_html = ""
    if result["reasons"]:
        items = "".join(f"<li>{html.escape(reason)}</li>" for reason in result["reasons"])
        reasons_html = f"<ul class='guide-card-reasons'>{items}</ul>"

    st.markdown(
        f"<div class='guide-card guide-card-{result['level']}'>"
        f"<div class='guide-card-label'>오늘의 가이드</div>"
        f"<div class='guide-card-headline'>{result['emoji']} {result['headline']}</div>"
        f"{reasons_html}"
        f"<div class='guide-card-suggestion'>{result['suggestion']}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_week_mood_strip(df: pd.DataFrame) -> None:
    mood_by_date = {}
    if not df.empty:
        for _, row in df.iterrows():
            mood_by_date[row["날짜"].date()] = str(row["마음 날씨"])

    today = today_kst()
    parts = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        emoji = MOOD_EMOJI.get(mood_by_date.get(day, ""))
        parts.append(emoji if emoji else "<span style='color:#c4cfc9'>●</span>")
    strip = "&nbsp;".join(parts)
    st.markdown(
        f"<div class='small-note'>최근 7일 마음 날씨&nbsp;&nbsp;<span style='font-size:1.15rem'>{strip}</span></div>",
        unsafe_allow_html=True,
    )


def render_recovery_note(df: pd.DataFrame) -> None:
    if had_recovery_yesterday(df):
        st.success("🌈 어제는 회복의 신호가 있었네요")


def render_pattern_section(df: pd.DataFrame) -> None:
    st.subheader("패턴")
    messages = []
    pilates_message = calc_pilates_external_stat(df)
    if pilates_message:
        messages.append(pilates_message)
    sleep_message = calc_sleep_evening_pattern(df)
    if sleep_message:
        messages.append(sleep_message)
    messages.extend(calc_symptom_mood_patterns(df))
    medication_message = calc_medication_mood_pattern(df)
    if medication_message:
        messages.append(medication_message)

    if not messages:
        st.caption("기록이 쌓이면 패턴을 알려드려요")
        return

    st.markdown("<div class='guide-box'>" + "<br>".join(messages) + "</div>", unsafe_allow_html=True)


def render_symptom_timeline(df: pd.DataFrame) -> None:
    st.subheader("증상 발생 추이")
    recent_30 = recent_days(df, 30)
    level_colors = {"보통": "#dfb75c", "심함": "#c96a55"}
    points = {"보통": [], "심함": []}
    if not recent_30.empty:
        for _, row in recent_30.iterrows():
            for symptom in SYMPTOM_TYPES:
                level = row.get(SYMPTOM_COLUMN_MAP[symptom])
                if level in points:
                    points[level].append((row["날짜"], symptom))

    if not points["보통"] and not points["심함"]:
        st.info("최근 30일 증상 기록이 없어요.")
        return

    fig = go.Figure()
    for level in ("보통", "심함"):
        if not points[level]:
            continue
        dates, symptoms = zip(*points[level])
        fig.add_trace(
            go.Scatter(
                x=list(dates),
                y=list(symptoms),
                mode="markers",
                name=level,
                marker=dict(size=13, color=level_colors[level], symbol="square"),
            )
        )
    fig.update_layout(
        title="최근 30일 증상 타임라인",
        height=280,
        margin=dict(l=8, r=8, t=52, b=20),
        xaxis_title="날짜",
        yaxis=dict(categoryorder="array", categoryarray=list(reversed(SYMPTOM_TYPES))),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    st.plotly_chart(fig, use_container_width=True, key="symptom_timeline_chart")


def render_sleep_trend(df: pd.DataFrame) -> None:
    st.subheader("수면 점수 추이")
    recent_30 = recent_days(df, 30)
    if not recent_30.empty:
        recent_30 = recent_30.dropna(subset=["수면 점수"])
    if recent_30.empty:
        st.info("기록이 쌓이면 수면 추이를 보여드려요")
        return

    fig = go.Figure(
        go.Scatter(
            x=recent_30["날짜"],
            y=recent_30["수면 점수"],
            mode="lines+markers",
            name="수면 점수",
            line=dict(width=3, color="#4c8a72"),
        )
    )

    vital_days = recent_30[recent_30["활력징후 이상"]]
    if not vital_days.empty:
        fig.add_trace(
            go.Scatter(
                x=vital_days["날짜"],
                y=vital_days["수면 점수"],
                mode="markers",
                name="활력징후 이상",
                marker=dict(size=14, color="#c96a55", symbol="x"),
            )
        )

    fig.add_hline(y=SLEEP_LOW_THRESHOLD, line=dict(color="#c4cfc9", width=1, dash="dot"))
    fig.update_layout(
        title="최근 30일 수면 점수",
        height=300,
        margin=dict(l=8, r=8, t=52, b=20),
        xaxis_title="날짜",
        yaxis_title="점수",
        yaxis=dict(range=[0, 100]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    st.plotly_chart(fig, use_container_width=True, key="sleep_trend_chart")


def render_evening_trend(df: pd.DataFrame) -> None:
    st.subheader("저녁 컨디션 추이")
    recent_30 = recent_days(df, 30)
    if not recent_30.empty:
        recent_30 = recent_30.dropna(subset=["저녁 컨디션"])
    if recent_30.empty:
        st.info("아직 저녁 컨디션 기록이 없어요.")
        return

    fig = go.Figure(
        go.Scatter(
            x=recent_30["날짜"],
            y=recent_30["저녁 컨디션"],
            mode="lines+markers",
            name="저녁 컨디션",
            line=dict(width=3, color="#4c8a72"),
        )
    )
    fig.update_layout(
        title="최근 30일 저녁 컨디션",
        height=300,
        margin=dict(l=8, r=8, t=52, b=20),
        xaxis_title="날짜",
        yaxis_title="점수",
        yaxis=dict(range=[0.5, 5.5], dtick=1),
    )
    st.plotly_chart(fig, use_container_width=True, key="evening_trend_chart")


def render_today_status_summary(exercise_type: str, evening_condition: int, med_status: dict, streak: int) -> None:
    st.subheader("기록 요약")
    row1_col1, row1_col2 = st.columns(2)
    row2_col1, row2_col2 = st.columns(2)
    row1_col1.metric("🏃 운동", exercise_type)
    row1_col2.metric("🌙 저녁 컨디션", f"{evening_condition} / 5")
    row2_col1.metric("💊 복용", f"{med_status['day_count']}일째" if med_status["medicating"] else "안 함")
    row2_col2.metric("🔥 연속 기록일", f"{streak}일")


def render_mood_buttons(existing: pd.Series | None) -> str:
    if "mood_choice" not in st.session_state:
        st.session_state["mood_choice"] = (
            existing["마음 날씨"]
            if existing is not None and existing["마음 날씨"] in MOOD_OPTIONS
            else MOOD_OPTIONS[0]
        )

    st.markdown("**마음 날씨**")
    with st.container(key="mood_grid"):
        for index, mood_name in enumerate(MOOD_OPTIONS):
            selected = st.session_state["mood_choice"] == mood_name
            label = f"{MOOD_EMOJI[mood_name]} {mood_name}\n\n{MOOD_DESCRIPTIONS[mood_name]}"
            if st.button(
                label,
                key=f"mood_btn_{index}",
                type="primary" if selected else "secondary",
                use_container_width=True,
            ):
                st.session_state["mood_choice"] = mood_name
                st.rerun()
    return st.session_state["mood_choice"]


def render_reflection_fields(existing: pd.Series | None) -> dict:
    st.subheader("3분 회고")
    good_job = st.text_area(
        "오늘 잘한 일",
        value=existing["오늘 잘한 일"] if existing is not None else "",
        max_chars=300,
        height=90,
        placeholder="작아도 괜찮습니다. 오늘 내가 잘해낸 일을 적어보세요.",
    )
    gratitude = st.text_area(
        "감사한 일",
        value=existing["감사한 일"] if existing is not None else "",
        max_chars=300,
        height=90,
        placeholder="사람, 상황, 나 자신에게 고마웠던 일을 적어보세요.",
    )
    learning = st.text_area(
        "배운 점",
        value=existing["배운 점"] if existing is not None else "",
        max_chars=300,
        height=90,
        placeholder="오늘 알게 된 것, 다음에 다르게 해보고 싶은 점을 적어보세요.",
    )
    tomorrow_focus = st.text_area(
        "내일 가장 중요한 한 가지",
        value=existing["내일 가장 중요한 한 가지"] if existing is not None else "",
        max_chars=300,
        height=90,
        placeholder="내일 이것 하나만 챙긴다면 무엇일까요?",
    )

    return {
        "오늘 잘한 일": good_job,
        "감사한 일": gratitude,
        "배운 점": learning,
        "내일 가장 중요한 한 가지": tomorrow_focus,
    }


def _existing_int(existing: pd.Series | None, column: str) -> int | None:
    if existing is None:
        return None
    value = existing.get(column)
    return None if value is None or pd.isna(value) else int(value)


def render_body_signal_section(existing: pd.Series | None) -> dict:
    st.subheader("몸 신호")
    sleep_score = st.number_input(
        "수면 점수 (애플워치)",
        min_value=0,
        max_value=100,
        step=1,
        value=_existing_int(existing, "수면 점수"),
        placeholder="0~100 점수를 입력해 주세요",
    )
    guide_lines = [f"{tier['min']} 이상 = {tier['label']}" for tier in SLEEP_TIERS[:-1]]
    guide_lines.append(f"{SLEEP_TIERS[-2]['min']} 미만 = {SLEEP_TIERS[-1]['label']}")
    st.markdown("<div class='guide-box'>" + "<br>".join(guide_lines) + "</div>", unsafe_allow_html=True)

    with st.expander("수면 세부 점수 (선택)", expanded=False):
        st.caption("비워두어도 저장됩니다. 나중에 어떤 요소가 컨디션에 영향이 큰지 살펴볼 때 쓰여요.")
        detail_col1, detail_col2, detail_col3 = st.columns(3)
        duration_score = detail_col1.number_input(
            "지속 시간", min_value=0, max_value=100, step=1,
            value=_existing_int(existing, "수면_지속시간"), placeholder="선택",
        )
        bedtime_score = detail_col2.number_input(
            "취침 시간", min_value=0, max_value=100, step=1,
            value=_existing_int(existing, "수면_취침시간"), placeholder="선택",
        )
        interruption_score = detail_col3.number_input(
            "수면 중단", min_value=0, max_value=100, step=1,
            value=_existing_int(existing, "수면_중단"), placeholder="선택",
        )

    default_vital = bool(existing["활력징후 이상"]) if existing is not None else False
    vital_abnormal = st.checkbox("심박수·호흡수 이상 알림 있었음", value=default_vital)
    vital_note = ""
    if vital_abnormal:
        vital_note = st.text_input(
            "어떤 이상이었나요 (선택)",
            value=str(existing["활력징후 메모"]) if existing is not None else "",
            max_chars=100,
            placeholder="예: 자는 중 심박수 알림",
        )

    return {
        "수면 점수": "" if sleep_score is None else sleep_score,
        "수면_지속시간": "" if duration_score is None else duration_score,
        "수면_취침시간": "" if bedtime_score is None else bedtime_score,
        "수면_중단": "" if interruption_score is None else interruption_score,
        "활력징후 이상": "O" if vital_abnormal else "X",
        "활력징후 메모": vital_note,
    }


def render_exercise_section(existing: pd.Series | None, history_df: pd.DataFrame) -> dict:
    st.subheader("운동 로그")
    exercise_default = (
        EXERCISE_TYPES.index(existing["운동 종류"])
        if existing is not None and existing["운동 종류"] in EXERCISE_TYPES
        else len(EXERCISE_TYPES) - 1
    )
    exercise_type = st.selectbox("운동 종류", EXERCISE_TYPES, index=exercise_default)

    exercise_time = ""
    intensity = ""
    has_external_schedule = ""

    if exercise_type != "안 함":
        default_time = DEFAULT_PILATES_TIME if exercise_type == "필라테스" else DEFAULT_EXERCISE_TIME
        if existing is not None and existing["운동 시간대"]:
            try:
                default_time = datetime.strptime(str(existing["운동 시간대"]), "%H:%M").time()
            except ValueError:
                pass
        time_value = st.time_input("운동 시간대", value=default_time)
        exercise_time = time_value.strftime("%H:%M")

        intensity_default = (
            INTENSITY_OPTIONS.index(existing["운동 강도"])
            if existing is not None and existing["운동 강도"] in INTENSITY_OPTIONS
            else 1
        )
        intensity = st.selectbox("강도", INTENSITY_OPTIONS, index=intensity_default)

        schedule_default = (
            EXTERNAL_SCHEDULE_OPTIONS.index(existing["외부 일정 여부"])
            if existing is not None and existing["외부 일정 여부"] in EXTERNAL_SCHEDULE_OPTIONS
            else 1
        )
        has_external_schedule = st.radio(
            "운동 후 외부 일정 여부", EXTERNAL_SCHEDULE_OPTIONS, index=schedule_default, horizontal=True
        )

        if exercise_type == "필라테스" and has_external_schedule == "있음":
            st.info("오늘 저녁은 가볍게 조정해보세요 (참고용)")

    evening_default = to_int(existing["저녁 컨디션"], 3) if existing is not None else 3
    evening_condition = st.slider("저녁 컨디션 자기평가", min_value=1, max_value=5, value=evening_default)

    stat_message = calc_pilates_external_stat(history_df)
    if stat_message:
        st.caption(stat_message)

    return {
        "운동 종류": exercise_type,
        "운동 시간대": exercise_time,
        "운동 강도": intensity,
        "외부 일정 여부": has_external_schedule,
        "저녁 컨디션": evening_condition,
    }


def render_medication_section(existing: pd.Series | None, history_df: pd.DataFrame) -> dict:
    st.subheader("약 & 증상 체크")
    default_taken = existing is not None and existing["약 복용 여부"] == "O"
    medication_taken = st.checkbox("약 복용", value=default_taken)

    med_status = get_medication_status(history_df)
    st.caption(f"복용 {med_status['day_count']}일째" if med_status["medicating"] else "복용 안 함")

    st.markdown("**증상 체크**")
    symptom_fields = {}
    other_label = existing["증상_기타명"] if existing is not None else ""
    for symptom in SYMPTOM_TYPES:
        column_name = SYMPTOM_COLUMN_MAP[symptom]
        default_level = (
            existing[column_name]
            if existing is not None and existing.get(column_name) in SYMPTOM_LEVELS
            else "없음"
        )
        level = st.select_slider(symptom, SYMPTOM_LEVELS, value=default_level)
        symptom_fields[column_name] = level
        if symptom == "기타":
            other_label = st.text_input("기타 증상 이름", value=other_label)

    return {
        "약 복용 여부": "O" if medication_taken else "X",
        "복용 시작일": "",  # 컬럼은 보존하되 더 이상 사용하지 않음
        "증상_기타명": other_label,
        **symptom_fields,
    }


def render_record_form(existing: pd.Series | None, streak: int, history_df: pd.DataFrame) -> None:
    # 아침 루틴: 기본값은 "어제 하루"에 대한 기록 (날짜를 바꾸면 그 날짜로 저장)
    st.subheader("어제 하루 기록")
    selected_date = st.date_input("날짜", value=today_kst() - timedelta(days=1))
    mood = render_mood_buttons(existing)
    st.divider()
    body_signal_fields = render_body_signal_section(existing)
    st.divider()
    exercise_fields = render_exercise_section(existing, history_df)
    st.divider()
    medication_fields = render_medication_section(existing, history_df)
    st.divider()
    reflection_fields = render_reflection_fields(existing)

    if st.button("💾 기록 저장", use_container_width=True):
        if body_signal_fields["수면 점수"] == "":
            st.warning("수면 점수를 입력해 주세요.")
        else:
            record = {
                "날짜": selected_date.strftime("%Y-%m-%d"),
                "마음 날씨": mood,
                **mood_fields_for(mood),
                **body_signal_fields,
                **reflection_fields,
                **exercise_fields,
                **medication_fields,
                "저장 시간": now_kst().isoformat(timespec="seconds"),
            }
            st.session_state["last_saved_record"] = record
            st.success(save_reflection(record))
            st.rerun()

    saved = st.session_state.get("last_saved_record")
    if saved:
        summary_exercise = saved["운동 종류"]
        summary_evening = to_int(saved["저녁 컨디션"], exercise_fields["저녁 컨디션"])
    else:
        summary_exercise = exercise_fields["운동 종류"]
        summary_evening = exercise_fields["저녁 컨디션"]

    render_today_status_summary(summary_exercise, summary_evening, get_medication_status(history_df), streak)


# delta_style — up_good: 증가=초록, down_good: 증가=주황/감소=초록, neutral: 회색
INBODY_TREND_SPECS = [
    {"label": "체중", "column": "체중", "delta_style": "neutral"},
    {"label": "골격근량", "column": "골격근량", "delta_style": "up_good"},
    {"label": "체지방량", "column": "body_fat_mass", "delta_style": "down_good"},
]
DELTA_GREEN = "#2e7d54"
DELTA_ORANGE = "#d98324"
DELTA_GRAY = "#66736d"


def _inbody_delta_html(diff: float | None, delta_style: str) -> str:
    if diff is None:
        return ""
    if delta_style == "neutral" or diff == 0:
        color = DELTA_GRAY
    elif delta_style == "up_good":
        color = DELTA_GREEN if diff > 0 else DELTA_ORANGE
    else:
        color = DELTA_ORANGE if diff > 0 else DELTA_GREEN
    return f" <span style='color:{color}'>({diff:+.1f})</span>"


def render_inbody_trend(inbody_df: pd.DataFrame) -> None:
    if inbody_df.empty:
        st.info("아직 인바디 기록이 없습니다.")
        return

    x_min, x_max = inbody_df["날짜"].min(), inbody_df["날짜"].max()
    x_pad = max((x_max - x_min) * 0.05, pd.Timedelta(days=1))
    x_range = [x_min - x_pad, x_max + x_pad]

    cols = st.columns(3)
    for col, spec in zip(cols, INBODY_TREND_SPECS):
        with col:
            series_df = inbody_df.dropna(subset=[spec["column"]])
            if series_df.empty:
                st.markdown(f"<div class='inbody-mini-title'>{spec['label']} -</div>", unsafe_allow_html=True)
                st.caption("아직 기록이 없어요")
                continue

            values = series_df[spec["column"]]
            latest = float(values.iloc[-1])
            diff = float(values.iloc[-1] - values.iloc[-2]) if len(values) >= 2 else None
            st.markdown(
                f"<div class='inbody-mini-title'>{spec['label']} {latest:.1f}kg"
                f"{_inbody_delta_html(diff, spec['delta_style'])}</div>",
                unsafe_allow_html=True,
            )

            if len(series_df) <= 1:
                st.caption("다음 측정부터 변화를 보여드려요")
                continue

            y_min, y_max = float(values.min()), float(values.max())
            y_pad = max((y_max - y_min) * 0.2, 0.5)
            fig = go.Figure(
                go.Scatter(
                    x=series_df["날짜"],
                    y=values,
                    mode="lines+markers",
                    line=dict(width=3, color="#4c8a72"),
                )
            )
            fig.update_layout(
                height=230,
                margin=dict(l=8, r=8, t=10, b=10),
                showlegend=False,
                xaxis=dict(range=x_range),
                yaxis=dict(range=[y_min - y_pad, y_max + y_pad]),
            )
            st.plotly_chart(fig, use_container_width=True, key=f"inbody_trend_{spec['column']}")


def render_inbody_delta_metrics(inbody_df: pd.DataFrame) -> None:
    deltas = calc_inbody_delta(inbody_df)
    if not deltas:
        return
    # 체지방량은 증가가 주의 신호이므로 delta 색상을 반전(증가=경고색, 감소=초록)
    metric_specs = [
        ("체중", "체중", "off"),
        ("골격근량", "골격근량", "normal"),
        ("body_fat_mass", "체지방량", "inverse"),
    ]
    cols = st.columns(3)
    for col, (column, label, delta_color) in zip(cols, metric_specs):
        info = deltas.get(column)
        if not info:
            col.metric(label, "-")
            continue
        diff = info["diff"]
        col.metric(
            label,
            f"{info['latest']:.1f} kg",
            delta=None if diff is None else f"{diff:+.1f} kg",
            delta_color="off" if diff is None else delta_color,
        )


def render_inbody_section(inbody_df: pd.DataFrame) -> None:
    st.caption("측정한 날에만 입력해 주세요.")

    col1, col2 = st.columns(2)
    with col1:
        measured_date = st.date_input("측정 날짜", value=today_kst(), key="inbody_date")
        weight = st.number_input("체중 (kg)", min_value=0.0, step=0.1, format="%.1f", key="inbody_weight")
    with col2:
        muscle_mass = st.number_input("골격근량 (kg)", min_value=0.0, step=0.1, format="%.1f", key="inbody_muscle")
        fat_mass = st.number_input("체지방량 (kg)", min_value=0.0, step=0.1, format="%.1f", key="inbody_fat_mass")

    if st.button("📏 인바디 저장", use_container_width=True):
        if weight == 0 and muscle_mass == 0 and fat_mass == 0:
            st.warning("측정값을 입력해 주세요.")
        else:
            record = {
                "날짜": measured_date.strftime("%Y-%m-%d"),
                "체중": weight,
                "골격근량": muscle_mass,
                "체지방률": "",
                "body_fat_mass": fat_mass,
                "저장 시간": now_kst().isoformat(timespec="seconds"),
            }
            st.success(save_inbody(record))
            st.rerun()

    render_inbody_delta_metrics(inbody_df)


def render_records_expander(df: pd.DataFrame) -> None:
    with st.expander("전체 기록 보기", expanded=False):
        if df.empty:
            st.info("아직 저장된 기록이 없습니다.")
            return
        display_df = df.copy()
        display_df["날짜"] = display_df["날짜"].dt.strftime("%Y-%m-%d")
        st.dataframe(display_df.sort_values("날짜", ascending=False), use_container_width=True, hide_index=True)


# ---------- App ----------
st.title("🌱 오늘의 나")
st.caption("하루를 가볍게 돌아보는 3분 기록")

if not has_google_sheet_settings():
    st.error("Google Sheets 연결 설정이 없습니다. Streamlit Secrets를 먼저 설정해주세요.")
    st.stop()

try:
    df = load_reflections()
    inbody_df = load_inbody()
except Exception as exc:
    st.error(f"Google Sheets에서 기록을 불러오지 못했습니다: {exc}")
    st.stop()

# 기본 편집 대상은 어제(KST) 기록 — 이미 저장돼 있으면 폼에 미리 채워진다
yesterday_text = (today_kst() - timedelta(days=1)).strftime("%Y-%m-%d")
yesterday_record = df[df["날짜"].dt.strftime("%Y-%m-%d") == yesterday_text] if not df.empty else pd.DataFrame()
existing_record = yesterday_record.iloc[-1] if not yesterday_record.empty else None
streak = get_streak_days(df)

today_tab, review_tab = st.tabs(["오늘", "돌아보기"])

with today_tab:
    render_today_guide(df)
    render_recovery_note(df)
    render_record_form(existing_record, streak, df)

    with st.expander("📏 인바디 입력 (측정한 날만)", expanded=False):
        render_inbody_section(inbody_df)

with review_tab:
    render_week_mood_strip(df)
    st.divider()

    st.subheader("인바디 추이")
    render_inbody_trend(inbody_df)
    st.divider()

    render_pattern_section(df)
    st.divider()

    render_sleep_trend(df)
    st.divider()

    render_symptom_timeline(df)
    st.divider()

    render_evening_trend(df)
    render_records_expander(df)
