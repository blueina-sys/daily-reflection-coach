import unittest

from logic import (
    CURRENT_COLUMNS,
    INBODY_CURRENT_COLUMNS,
    INBODY_V1_COLUMNS,
    LEGACY_COLUMNS,
    V1_COLUMNS,
    V2_COLUMNS,
    backfill_mood_fields,
    build_migrated_inbody_rows,
    build_migrated_rows,
    evaluate_guide,
    mood_fields_for,
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


if __name__ == "__main__":
    unittest.main()
