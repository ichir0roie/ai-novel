#!/usr/bin/env python3
"""time_keeper 配下の各生成器が使う、確率・年齢・件数などのハードコードされた値をまとめる。"""
from __future__ import annotations

# _format
MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)

# character_lifespan
# 老衰。この歳を過ぎるまでは自然死しない。
NATURAL_DEATH_MIN_AGE = 50
# この歳に達したら、老衰は必ず起きる(不老でない限り)。
NATURAL_DEATH_MAX_AGE = 150
# 事故。年齢によらず、年に一度この確率で起きうる(不死でない限り)。
ACCIDENT_PROBABILITY_PER_YEAR = 0.003

# random_character_generator
CHARACTER_PROBABILITY = 0.1  # 1月に1度、必ず一人
# 生成時点での年齢の幅。0(赤子)ではなく、この範囲でランダムに選んだ年数だけ
# 過去に生まれたことにする(NATURAL_DEATH_MIN_AGE の50歳より十分若い範囲に
# 収め、生成直後に老衰死しないようにする)。
CHARACTER_AGE_RANGE = (0, 40)
# 生成する一件が人物以外の対象(国・組織など)になる確率。当たったら種別は AI に選ばせる。
NON_PERSON_PROBABILITY = 0.3
NON_PERSON_KINDS = ("国", "組織", "商会", "氏族", "集団", "物")
# 人物以外の対象に AI へ選ばせる「どこまで届くか」と、それを落とす world_influence の値。
# 数そのものを AI に決めさせない(尺度が決まっていないため)。
SCALE_INFLUENCE = {
    "集落内": 0,
    "地域": 1,
    "国": 2,
    "大陸": 3,
}
DEFAULT_SCALE = "地域"

# random_location_generator
LOCATION_PROBABILITY = 0.01  # 1年に1度、1%の確率で

# event_progression_generator
PLACE_PROBABILITY = 0.75
# 移動先候補(_move_destinations)をどこまで拾うか。read_cast の既定
# (levels=1、「隣の集落にいる者も枠に入れる」)と同じ考え方をそろえる。
REACH_LEVELS = 1
MOVE_DESTINATION_LIMIT = 20
# event_duration_days の取りうる範囲。範囲外の値は丸める。
EVENT_DURATION_RANGE_DAYS = (1, 90)
DEFAULT_EVENT_DURATION_DAYS = 1
# サイコロで選ぶ候補の件数。少ないと交渉型の無難な候補だけで埋まり、
# 多いと本文を書く段で候補の要約が薄くなる。
CANDIDATE_COUNT = 6
TRAIT_COLUMNS = (
    "sincerity", "curiosity", "proactivity", "cooperativeness", "sociability",
    "emotional_expression", "self_esteem", "self_efficacy", "stress_resilience",
    "flexibility_of_values", "sensitivity", "imagination",
)


MAX_CHARACTER_PLOT_PER_LOCATION = 5
