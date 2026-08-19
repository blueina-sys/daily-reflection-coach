import unittest
from datetime import date, datetime, timedelta, timezone

from logic import (
    KST,
    CURRENT_COLUMNS,
    INBODY_CURRENT_COLUMNS,
    INBODY_V1_COLUMNS,
    LEGACY_COLUMNS,
    V1_COLUMNS,
    V2_COLUMNS,
    V3_COLUMNS,
    V4_COLUMNS,
    detect_ulcer_episodes,
    mouth_ulcer_alert,
    ulcer_response_comparison,
    sleep_evening_gap,
    sleep_guide_score,
    sleep_tier,
    backfill_mood_fields,
    build_migrated_inbody_rows,
    build_migrated_rows,
    evaluate_guide,
    medication_status,
    mood_fields_for,
    now_kst,
    today_kst,
)


def row_dict(row: list) -> dict:
    return dict(zip(CURRENT_COLUMNS, row))


class MoodFieldsTest(unittest.TestCase):
    def test_score_mapping(self):
        expected = {
            "맑음": 3,
            "무지개": 3,
            "구름 조금": 2,
            "비 온 뒤 갬": 2,
            "흐림": 1,
            "가벼운 비": 1,
            "폭우": 0,
        }
        for mood, score in expected.items():
            self.assertEqual(mood_fields_for(mood)["mood_score"], score, mood)

    def test_recovery_tag_only_for_recovery_moods(self):
        self.assertEqual(mood_fields_for("비 온 뒤 갬")["recovery_tag"], "TRUE")
        self.assertEqual(mood_fields_for("무지개")["recovery_tag"], "TRUE")
        for mood in ("맑음", "구름 조금", "흐림", "가벼운 비", "폭우"):
            self.assertEqual(mood_fields_for(mood)["recovery_tag"], "FALSE", mood)

    def test_unknown_mood_leaves_fields_empty(self):
        self.assertEqual(mood_fields_for(""), {"mood_score": "", "recovery_tag": ""})
        self.assertEqual(mood_fields_for("안개"), {"mood_score": "", "recovery_tag": ""})

    def test_backfill_keeps_existing_score(self):
        row = {"마음 날씨": "폭우", "mood_score": 2, "recovery_tag": "FALSE"}
        backfill_mood_fields(row)
        self.assertEqual(row["mood_score"], 2)

    def test_backfill_fills_missing_score(self):
        row = {"마음 날씨": "무지개", "mood_score": ""}
        backfill_mood_fields(row)
        self.assertEqual(row["mood_score"], 3)
        self.assertEqual(row["recovery_tag"], "TRUE")


class BuildMigratedRowsTest(unittest.TestCase):
    def test_current_header_needs_no_migration(self):
        self.assertIsNone(build_migrated_rows([CURRENT_COLUMNS, [""] * len(CURRENT_COLUMNS)]))

    def test_unknown_header_returns_none(self):
        self.assertIsNone(build_migrated_rows([["A", "B", "C"], ["1", "2", "3"]]))

    def test_empty_values_returns_none(self):
        self.assertIsNone(build_migrated_rows([]))

    def test_v2_migration_backfills_mood_columns(self):
        source = dict(zip(V2_COLUMNS, [""] * len(V2_COLUMNS)))
        source.update(
            {
                "날짜": "2026-07-01",
                "마음 날씨": "무지개",
                "오늘 잘한 일": "산책",
                "운동 종류": "필라테스",
                "저녁 컨디션": "4",
                "약 복용 여부": "O",
            }
        )
        values = [V2_COLUMNS, [source[c] for c in V2_COLUMNS]]

        migrated = build_migrated_rows(values)
        self.assertIsNotNone(migrated)
        self.assertEqual(migrated[0], CURRENT_COLUMNS)
        row = row_dict(migrated[1])
        self.assertEqual(row["날짜"], "2026-07-01")
        self.assertEqual(row["마음 날씨"], "무지개")
        self.assertEqual(row["mood_score"], 3)
        self.assertEqual(row["recovery_tag"], "TRUE")
        self.assertEqual(row["오늘 잘한 일"], "산책")
        self.assertEqual(row["운동 종류"], "필라테스")
        self.assertEqual(row["저녁 컨디션"], "4")
        self.assertEqual(row["약 복용 여부"], "O")

    def test_v2_migration_without_mood_leaves_empty(self):
        blank = [""] * len(V2_COLUMNS)
        blank[0] = "2026-07-02"
        migrated = build_migrated_rows([V2_COLUMNS, blank])
        row = row_dict(migrated[1])
        self.assertEqual(row["mood_score"], "")
        self.assertEqual(row["recovery_tag"], "")

    def test_v1_migration_backfills_mood_columns(self):
        source = dict(zip(V1_COLUMNS, [""] * len(V1_COLUMNS)))
        source.update({"날짜": "2026-05-01", "마음 날씨": "폭우", "감사한 일": "커피"})
        migrated = build_migrated_rows([V1_COLUMNS, [source[c] for c in V1_COLUMNS]])
        row = row_dict(migrated[1])
        self.assertEqual(row["mood_score"], 0)
        self.assertEqual(row["recovery_tag"], "FALSE")
        self.assertEqual(row["감사한 일"], "커피")
        self.assertNotIn("활동 에너지", CURRENT_COLUMNS)

    def test_legacy_migration_renames_and_backfills(self):
        values = [
            LEGACY_COLUMNS,
            ["2026-04-01", "7", "3", "비 온 뒤 갬", "발표를 마쳤다", "반신욕"],
        ]
        migrated = build_migrated_rows(values)
        row = row_dict(migrated[1])
        self.assertEqual(row["오늘 잘한 일"], "발표를 마쳤다")
        self.assertEqual(row["배운 점"], "반신욕")
        self.assertEqual(row["mood_score"], 2)
        self.assertEqual(row["recovery_tag"], "TRUE")

    def test_short_rows_are_padded(self):
        migrated = build_migrated_rows([LEGACY_COLUMNS, ["2026-04-02", "5"]])
        row = row_dict(migrated[1])
        self.assertEqual(row["날짜"], "2026-04-02")
        self.assertEqual(row["마음 날씨"], "")
        self.assertEqual(row["mood_score"], "")


class BuildMigratedInbodyRowsTest(unittest.TestCase):
    def test_current_header_needs_no_migration(self):
        self.assertIsNone(
            build_migrated_inbody_rows([INBODY_CURRENT_COLUMNS, [""] * len(INBODY_CURRENT_COLUMNS)])
        )

    def test_unknown_header_returns_none(self):
        self.assertIsNone(build_migrated_inbody_rows([["A", "B"], ["1", "2"]]))

    def test_empty_values_returns_none(self):
        self.assertIsNone(build_migrated_inbody_rows([]))

    def test_v1_migration_preserves_fat_percent_and_saved_time(self):
        values = [
            INBODY_V1_COLUMNS,
            ["2026-07-01", "60.0", "24.5", "28.3", "2026-07-01T08:00:00"],
        ]
        migrated = build_migrated_inbody_rows(values)
        self.assertEqual(migrated[0], INBODY_CURRENT_COLUMNS)
        row = dict(zip(INBODY_CURRENT_COLUMNS, migrated[1]))
        self.assertEqual(row["날짜"], "2026-07-01")
        self.assertEqual(row["체중"], "60.0")
        self.assertEqual(row["골격근량"], "24.5")
        self.assertEqual(row["체지방률"], "28.3")
        self.assertEqual(row["body_fat_mass"], "")
        self.assertEqual(row["저장 시간"], "2026-07-01T08:00:00")

    def test_v1_short_rows_are_padded(self):
        migrated = build_migrated_inbody_rows([INBODY_V1_COLUMNS, ["2026-07-02", "59.5"]])
        row = dict(zip(INBODY_CURRENT_COLUMNS, migrated[1]))
        self.assertEqual(row["체중"], "59.5")
        self.assertEqual(row["체지방률"], "")
        self.assertEqual(row["body_fat_mass"], "")


class EvaluateGuideTest(unittest.TestCase):
    def test_no_signals_is_green(self):
        result = evaluate_guide({})
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["level"], "green")
        self.assertEqual(result["reasons"], [])

    def test_single_light_signal_stays_green(self):
        result = evaluate_guide({"medicating": True, "med_day_count": 3})
        self.assertEqual(result["score"], 1)
        self.assertEqual(result["level"], "green")
        self.assertIn("복용 3일째예요", result["reasons"])

    def test_pilates_external_is_yellow(self):
        result = evaluate_guide({"pilates_with_external": True})
        self.assertEqual(result["score"], 2)
        self.assertEqual(result["level"], "yellow")

    def test_three_points_is_yellow(self):
        result = evaluate_guide({"pilates_with_external": True, "moderate_symptoms": ["목 아픔"]})
        self.assertEqual(result["score"], 3)
        self.assertEqual(result["level"], "yellow")

    def test_four_points_is_red(self):
        result = evaluate_guide({"pilates_with_external": True, "severe_symptoms": ["구내염"]})
        self.assertEqual(result["score"], 4)
        self.assertEqual(result["level"], "red")
        self.assertIn("어제 구내염 증상이 심했어요", result["reasons"])

    def test_all_signals(self):
        result = evaluate_guide(
            {
                "pilates_with_external": True,
                "evening_condition": 1,
                "severe_symptoms": ["구내염"],
                "moderate_symptoms": ["피로감"],
                "medicating": True,
                "med_day_count": 10,
                "mood_score": 0,
            }
        )
        self.assertEqual(result["score"], 10)
        self.assertEqual(result["level"], "red")
        self.assertEqual(len(result["reasons"]), 6)

    def test_storm_mood_counts_only_zero(self):
        self.assertEqual(evaluate_guide({"mood_score": 0})["score"], 2)
        self.assertEqual(evaluate_guide({"mood_score": 1})["score"], 0)
        self.assertEqual(evaluate_guide({"mood_score": None})["score"], 0)

    def test_evening_condition_boundary(self):
        self.assertEqual(evaluate_guide({"evening_condition": 2})["score"], 2)
        self.assertEqual(evaluate_guide({"evening_condition": 3})["score"], 0)

    def test_pilates_without_external_is_info_only(self):
        result = evaluate_guide(
            {"pilates": True, "exercise_time": "10:00", "exercise_intensity": "보통"}
        )
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["level"], "green")
        self.assertIn("어제 필라테스를 했어요 (10:00 · 보통)", result["reasons"])

    def test_pilates_with_external_shows_single_bullet_with_detail(self):
        result = evaluate_guide(
            {
                "pilates": True,
                "pilates_with_external": True,
                "exercise_time": "10:00",
                "exercise_intensity": "힘듦",
            }
        )
        self.assertEqual(result["score"], 2)
        self.assertEqual(result["reasons"], ["어제 필라테스 후 외부 일정이 있었어요 (10:00 · 힘듦)"])


class KstDateTest(unittest.TestCase):
    """배포 서버가 UTC일 때 한국 아침 시간대의 날짜 계산 검증."""

    # 한국 시간 2026-07-20 08:00 = UTC 2026-07-19 23:00
    KOREAN_MORNING_8AM = datetime(2026, 7, 19, 23, 0, tzinfo=timezone.utc)

    def test_today_is_korean_date_not_utc_date(self):
        self.assertEqual(today_kst(self.KOREAN_MORNING_8AM), date(2026, 7, 20))

    def test_yesterday_for_guide_is_korean_yesterday(self):
        yesterday = today_kst(self.KOREAN_MORNING_8AM) - timedelta(days=1)
        self.assertEqual(yesterday, date(2026, 7, 19))

    def test_now_kst_clock_time(self):
        now = now_kst(self.KOREAN_MORNING_8AM)
        self.assertEqual((now.hour, now.minute), (8, 0))
        self.assertEqual(str(now.tzinfo), str(KST))

    def test_afternoon_utc_is_same_korean_day(self):
        # UTC 2026-07-19 14:59 = KST 23:59 → 아직 7/19
        afternoon = datetime(2026, 7, 19, 14, 59, tzinfo=timezone.utc)
        self.assertEqual(today_kst(afternoon), date(2026, 7, 19))

    def test_kst_midnight_boundary(self):
        # UTC 15:00 = KST 자정 → 다음 날로 넘어감
        boundary = datetime(2026, 7, 19, 15, 0, tzinfo=timezone.utc)
        self.assertEqual(today_kst(boundary), date(2026, 7, 20))


class SleepScoreTest(unittest.TestCase):
    def test_tier_labels_and_scores(self):
        cases = [
            (100, "매우 좋음", 0),
            (85, "매우 좋음", 0),
            (84, "양호", 1),
            (70, "양호", 1),
            (69, "부족", 2),
            (50, "부족", 2),
            (49, "많이 부족", 3),
            (0, "많이 부족", 3),
        ]
        for score, label, guide_score in cases:
            self.assertEqual(sleep_tier(score)["label"], label, score)
            self.assertEqual(sleep_guide_score(score), guide_score, score)

    def test_missing_sleep_score_is_ignored(self):
        for value in (None, "", "몰라"):
            self.assertIsNone(sleep_tier(value), value)
            self.assertEqual(sleep_guide_score(value), 0, value)

    def test_guide_adds_sleep_points_with_reason(self):
        result = evaluate_guide({"sleep_score": 45})
        self.assertEqual(result["score"], 3)
        self.assertEqual(result["level"], "yellow")
        self.assertEqual(result["reasons"], ["어젯밤 수면 점수가 45점으로 많이 부족했어요"])

    def test_guide_good_sleep_adds_nothing(self):
        result = evaluate_guide({"sleep_score": 90})
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["reasons"], [])

    def test_guide_vital_abnormal(self):
        result = evaluate_guide({"vital_abnormal": True})
        self.assertEqual(result["score"], 3)
        self.assertEqual(result["reasons"], ["활력 징후 이상 알림이 있었어요"])

    def test_guide_sleep_and_vital_combine_to_red(self):
        result = evaluate_guide({"sleep_score": 45, "vital_abnormal": True})
        self.assertEqual(result["score"], 6)
        self.assertEqual(result["level"], "red")
        self.assertEqual(len(result["reasons"]), 2)

    def test_guide_without_body_signals_is_unchanged(self):
        # 과거 기록처럼 수면/활력징후 값이 없어도 오류 없이 기존 점수만 계산
        result = evaluate_guide({"pilates_with_external": True})
        self.assertEqual(result["score"], 2)


class SleepEveningGapTest(unittest.TestCase):
    def test_returns_gap_when_enough_data(self):
        # 낮은 수면 5일(저녁 2점) + 높은 수면 5일(저녁 4점) → 2.0점 차이
        pairs = [(60, 2)] * 5 + [(80, 4)] * 5
        self.assertAlmostEqual(sleep_evening_gap(pairs), 2.0)

    def test_hidden_when_fewer_than_10_days(self):
        pairs = [(60, 2)] * 4 + [(80, 4)] * 5
        self.assertIsNone(sleep_evening_gap(pairs))

    def test_hidden_when_one_group_empty(self):
        self.assertIsNone(sleep_evening_gap([(80, 4)] * 12))

    def test_hidden_when_low_sleep_not_worse(self):
        pairs = [(60, 4)] * 5 + [(80, 3)] * 5
        self.assertIsNone(sleep_evening_gap(pairs))

    def test_rows_with_missing_values_are_skipped(self):
        pairs = [(60, 2)] * 5 + [(80, 4)] * 5 + [(None, 5), (70, None), ("", "")]
        self.assertAlmostEqual(sleep_evening_gap(pairs), 2.0)

    def test_threshold_boundary_70_counts_as_high(self):
        pairs = [(69, 2)] * 5 + [(70, 4)] * 5
        self.assertAlmostEqual(sleep_evening_gap(pairs), 2.0)


class BodySignalMigrationTest(unittest.TestCase):
    def test_v3_migration_leaves_body_signal_columns_empty(self):
        source = dict(zip(V3_COLUMNS, [""] * len(V3_COLUMNS)))
        source.update({"날짜": "2026-07-01", "마음 날씨": "맑음", "mood_score": "3", "저녁 컨디션": "4"})
        migrated = build_migrated_rows([V3_COLUMNS, [source[c] for c in V3_COLUMNS]])

        self.assertEqual(migrated[0], CURRENT_COLUMNS)
        row = dict(zip(CURRENT_COLUMNS, migrated[1]))
        self.assertEqual(row["날짜"], "2026-07-01")
        self.assertEqual(row["저녁 컨디션"], "4")
        self.assertEqual(row["수면 점수"], "")
        self.assertEqual(row["활력징후 이상"], "")
        self.assertEqual(row["활력징후 메모"], "")

    def test_older_schema_still_migrates_to_current(self):
        values = [LEGACY_COLUMNS, ["2026-04-01", "7", "3", "무지개", "발표", "반신욕"]]
        row = dict(zip(CURRENT_COLUMNS, build_migrated_rows(values)[1]))
        self.assertEqual(row["mood_score"], 3)
        self.assertEqual(row["오늘 잘한 일"], "발표")
        self.assertEqual(row["수면 점수"], "")


def ulcer_entry(day: int, level: str, medicated: str = "X", hospital: str = "") -> dict:
    return {"date": date(2026, 7, day), "level": level, "medicated": medicated, "hospital": hospital}


class MouthUlcerAlertTest(unittest.TestCase):
    def test_no_signal_hides_banner(self):
        self.assertIsNone(mouth_ulcer_alert({}))
        self.assertIsNone(mouth_ulcer_alert({"dry": False, "sting": False}))

    def test_sting_is_red(self):
        alert = mouth_ulcer_alert({"sting": True, "weekday": 0})
        self.assertEqual(alert["level"], "red")
        self.assertEqual(alert["headline"], "구내염 전조 가능성. 오늘 안에 대응하세요")
        self.assertEqual(alert["notes"], [])

    def test_sting_on_thursday_and_friday_adds_weekend_note(self):
        for weekday in (3, 4):
            alert = mouth_ulcer_alert({"sting": True, "weekday": weekday})
            self.assertEqual(
                alert["notes"], ["주말이 다가와요 — 병원 방문이나 약 시작을 미루지 마세요"], weekday
            )

    def test_dry_alone_is_not_enough(self):
        self.assertIsNone(mouth_ulcer_alert({"dry": True, "mood_score": 3, "sleep_score": 90}))

    def test_dry_with_each_trigger_is_yellow(self):
        triggers = [
            {"mood_score": 1},
            {"sleep_score": 69},
            {"fatigue_level": "보통"},
            {"irritation": True},
        ]
        for trigger in triggers:
            alert = mouth_ulcer_alert({"dry": True, **trigger})
            self.assertEqual(alert["level"], "yellow", trigger)
            self.assertEqual(alert["headline"], "구내염 주의 신호", trigger)
            self.assertIn("물 충분히 마시기", alert["notes"])

    def test_sting_takes_priority_over_dry(self):
        alert = mouth_ulcer_alert({"dry": True, "sting": True, "sleep_score": 50, "weekday": 0})
        self.assertEqual(alert["level"], "red")


class DetectUlcerEpisodesTest(unittest.TestCase):
    def test_no_episode_when_always_none(self):
        entries = [ulcer_entry(d, "없음") for d in range(1, 6)]
        self.assertEqual(detect_ulcer_episodes(entries), [])

    def test_start_detected_on_transition_to_active(self):
        entries = [ulcer_entry(1, "없음"), ulcer_entry(2, "없음"), ulcer_entry(3, "보통"), ulcer_entry(4, "심함")]
        episodes = detect_ulcer_episodes(entries)
        self.assertEqual(len(episodes), 1)
        self.assertEqual(episodes[0]["start"], date(2026, 7, 3))
        self.assertTrue(episodes[0]["ongoing"])
        self.assertEqual(episodes[0]["duration_days"], 2)

    def test_recovery_closes_episode(self):
        entries = [ulcer_entry(1, "보통"), ulcer_entry(2, "심함"), ulcer_entry(3, "보통"), ulcer_entry(4, "없음")]
        episode = detect_ulcer_episodes(entries)[0]
        self.assertFalse(episode["ongoing"])
        self.assertEqual(episode["duration_days"], 3)
        self.assertEqual(episode["last_active"], date(2026, 7, 3))

    def test_second_episode_gets_gap_days(self):
        entries = [
            ulcer_entry(1, "보통"), ulcer_entry(2, "없음"),
            ulcer_entry(10, "보통"), ulcer_entry(11, "없음"),
        ]
        episodes = detect_ulcer_episodes(entries)
        self.assertEqual(len(episodes), 2)
        self.assertIsNone(episodes[0]["gap_days"])
        self.assertEqual(episodes[1]["gap_days"], 9)

    def test_med_start_is_derived_from_medication_records(self):
        # 7/1 발생, 7/3부터 복용 시작 → 대응까지 2일, 병원 방문일도 같은 날로 본다
        entries = [
            ulcer_entry(1, "보통", medicated="X"),
            ulcer_entry(2, "보통", medicated="X"),
            ulcer_entry(3, "보통", medicated="O"),
            ulcer_entry(4, "보통", medicated="O"),
            ulcer_entry(5, "없음", medicated="O"),
        ]
        episode = detect_ulcer_episodes(entries)[0]
        self.assertEqual(episode["med_start"], date(2026, 7, 3))
        self.assertEqual(episode["hospital"], date(2026, 7, 3))
        self.assertFalse(episode["hospital_is_manual"])
        self.assertEqual(episode["response_days"], 2)
        self.assertEqual(episode["delay_days"], 2)

    def test_no_medication_means_not_responded_yet(self):
        entries = [ulcer_entry(1, "보통"), ulcer_entry(2, "보통"), ulcer_entry(3, "없음")]
        episode = detect_ulcer_episodes(entries)[0]
        self.assertIsNone(episode["med_start"])
        self.assertIsNone(episode["response_days"])
        self.assertIsNone(episode["hospital"])

    def test_medication_started_before_onset_gives_negative_response(self):
        entries = [
            ulcer_entry(1, "없음", medicated="O"),
            ulcer_entry(2, "없음", medicated="O"),
            ulcer_entry(3, "보통", medicated="O"),
            ulcer_entry(4, "없음", medicated="O"),
        ]
        episode = detect_ulcer_episodes(entries)[0]
        self.assertEqual(episode["med_start"], date(2026, 7, 1))
        self.assertEqual(episode["response_days"], -2)

    def test_manual_hospital_date_overrides_medication_date(self):
        # 집에 있던 약을 7/1에 먼저 시작하고 병원은 7/4에 간 예외 상황
        entries = [
            ulcer_entry(1, "보통", medicated="O"),
            ulcer_entry(2, "보통", medicated="O", hospital="2026-07-04"),
            ulcer_entry(5, "없음"),
        ]
        episode = detect_ulcer_episodes(entries)[0]
        self.assertEqual(episode["med_start"], date(2026, 7, 1))
        self.assertEqual(episode["response_days"], 0)
        self.assertEqual(episode["hospital"], date(2026, 7, 4))
        self.assertTrue(episode["hospital_is_manual"])
        self.assertEqual(episode["delay_days"], 3)

    def test_invalid_manual_hospital_date_is_ignored(self):
        entries = [ulcer_entry(1, "보통", medicated="O", hospital="몰라"), ulcer_entry(2, "없음")]
        episode = detect_ulcer_episodes(entries)[0]
        self.assertFalse(episode["hospital_is_manual"])
        self.assertEqual(episode["hospital"], date(2026, 7, 1))

    def test_previous_episode_medication_does_not_leak(self):
        entries = [
            ulcer_entry(1, "보통", medicated="O"),
            ulcer_entry(2, "없음", medicated="O"),
            ulcer_entry(3, "없음", medicated="X"),
            ulcer_entry(10, "보통", medicated="X"),
            ulcer_entry(11, "없음", medicated="X"),
        ]
        episodes = detect_ulcer_episodes(entries)
        self.assertEqual(episodes[0]["med_start"], date(2026, 7, 1))
        self.assertIsNone(episodes[1]["med_start"])

    def test_unsorted_entries_are_handled(self):
        entries = [ulcer_entry(4, "없음"), ulcer_entry(1, "보통"), ulcer_entry(2, "심함")]
        episode = detect_ulcer_episodes(entries)[0]
        self.assertEqual(episode["start"], date(2026, 7, 1))
        self.assertEqual(episode["duration_days"], 2)


class UlcerResponseComparisonTest(unittest.TestCase):
    def test_none_when_too_few_episodes(self):
        entries = [ulcer_entry(1, "보통", medicated="O"), ulcer_entry(2, "없음")]
        self.assertIsNone(ulcer_response_comparison(detect_ulcer_episodes(entries)))

    def test_fast_visits_show_shorter_duration(self):
        episodes = [
            {"delay_days": 0, "duration_days": 3, "ongoing": False},
            {"delay_days": 1, "duration_days": 4, "ongoing": False},
            {"delay_days": 5, "duration_days": 9, "ongoing": False},
            {"delay_days": 6, "duration_days": 11, "ongoing": False},
        ]
        result = ulcer_response_comparison(episodes)
        self.assertEqual(result["fast_count"], 2)
        self.assertEqual(result["slow_count"], 2)
        self.assertAlmostEqual(result["fast_avg_duration"], 3.5)
        self.assertAlmostEqual(result["slow_avg_duration"], 10.0)

    def test_ongoing_episode_is_excluded(self):
        episodes = [
            {"delay_days": 0, "duration_days": 3, "ongoing": False},
            {"delay_days": 5, "duration_days": 2, "ongoing": True},
        ]
        self.assertIsNone(ulcer_response_comparison(episodes))

    def test_none_when_all_delays_identical(self):
        episodes = [
            {"delay_days": 2, "duration_days": 5, "ongoing": False},
            {"delay_days": 2, "duration_days": 7, "ongoing": False},
        ]
        self.assertIsNone(ulcer_response_comparison(episodes))


class UlcerMigrationTest(unittest.TestCase):
    def test_v4_migration_leaves_ulcer_columns_empty(self):
        source = dict(zip(V4_COLUMNS, [""] * len(V4_COLUMNS)))
        source.update({"날짜": "2026-08-01", "마음 날씨": "맑음", "수면 점수": "80", "증상_구내염": "보통"})
        migrated = build_migrated_rows([V4_COLUMNS, [source[c] for c in V4_COLUMNS]])

        self.assertEqual(migrated[0], CURRENT_COLUMNS)
        row = dict(zip(CURRENT_COLUMNS, migrated[1]))
        self.assertEqual(row["수면 점수"], "80")
        self.assertEqual(row["증상_구내염"], "보통")
        for column in ["입안 건조", "입안 따끔", "구강 자극", "구강 자극 종류", "구내염_병원방문일", "구내염_약시작일"]:
            self.assertEqual(row[column], "", column)

    def test_oldest_schema_still_reaches_current(self):
        values = [LEGACY_COLUMNS, ["2026-04-01", "7", "3", "무지개", "발표", "반신욕"]]
        row = dict(zip(CURRENT_COLUMNS, build_migrated_rows(values)[1]))
        self.assertEqual(row["mood_score"], 3)
        self.assertEqual(row["입안 건조"], "")


class MedicationStatusTest(unittest.TestCase):
    def test_five_O_then_three_X_is_not_medicating(self):
        # O 5일 연속(7/1~7/5) 후 X 3일(7/6~7/8) → 복용 안 함
        entries = [(date(2026, 7, d), "O") for d in range(1, 6)]
        entries += [(date(2026, 7, d), "X") for d in range(6, 9)]
        status = medication_status(entries)
        self.assertFalse(status["medicating"])
        self.assertEqual(status["day_count"], 0)

    def test_resume_after_break_starts_at_day_1(self):
        # 위 시나리오에서 7/9에 다시 O → 복용 1일째로 새로 시작
        entries = [(date(2026, 7, d), "O") for d in range(1, 6)]
        entries += [(date(2026, 7, d), "X") for d in range(6, 9)]
        entries.append((date(2026, 7, 9), "O"))
        status = medication_status(entries)
        self.assertTrue(status["medicating"])
        self.assertEqual(status["day_count"], 1)

    def test_consecutive_O_counts_days(self):
        entries = [(date(2026, 7, d), "O") for d in range(1, 6)]
        status = medication_status(entries)
        self.assertTrue(status["medicating"])
        self.assertEqual(status["day_count"], 5)

    def test_one_missing_day_keeps_streak(self):
        # O(7/1), O(7/2), 기록 없음(7/3), O(7/4) → 연속 인정, 3일째
        entries = [(date(2026, 7, 1), "O"), (date(2026, 7, 2), "O"), (date(2026, 7, 4), "O")]
        status = medication_status(entries)
        self.assertTrue(status["medicating"])
        self.assertEqual(status["day_count"], 3)

    def test_two_missing_days_break_streak(self):
        # O(7/1), 기록 없음(7/2~7/3), O(7/4) → 연속 끊김, 1일째
        entries = [(date(2026, 7, 1), "O"), (date(2026, 7, 4), "O")]
        status = medication_status(entries)
        self.assertTrue(status["medicating"])
        self.assertEqual(status["day_count"], 1)

    def test_empty_or_blank_records(self):
        blank = {"medicating": False, "day_count": 0, "start_date": None}
        self.assertEqual(medication_status([]), blank)
        entries = [(date(2026, 7, 1), ""), (date(2026, 7, 2), " ")]
        self.assertEqual(medication_status(entries), blank)

    def test_start_date_is_first_day_of_current_streak(self):
        # 7/1~7/5 복용 → 중단 → 7/9부터 다시 복용: 시작일은 7/9
        entries = [(date(2026, 7, d), "O") for d in range(1, 6)]
        entries += [(date(2026, 7, d), "X") for d in range(6, 9)]
        entries += [(date(2026, 7, d), "O") for d in (9, 10)]
        status = medication_status(entries)
        self.assertEqual(status["start_date"], date(2026, 7, 9))
        self.assertEqual(status["day_count"], 2)

    def test_start_date_none_when_not_medicating(self):
        entries = [(date(2026, 7, 1), "O"), (date(2026, 7, 2), "X")]
        self.assertIsNone(medication_status(entries)["start_date"])

    def test_blank_latest_is_skipped(self):
        # 마지막 날 기록이 빈 값이면 그 이전의 O/X가 기준
        entries = [(date(2026, 7, 1), "O"), (date(2026, 7, 2), "")]
        status = medication_status(entries)
        self.assertTrue(status["medicating"])
        self.assertEqual(status["day_count"], 1)


if __name__ == "__main__":
    unittest.main()
