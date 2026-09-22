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
GENERATION_CHARACTER_PROBABILITY = 0.3
GENERATION_CHARACTER_AGE_RANGE = (0, 40)
# 命名時の重複回避に渡す「既にいる人物・対象」の上限。born_place とその祖先
# (国・大陸まで)全体の居住者を対象にするため、世界が育つほど際限なく
# 増える。上限が無いとプロンプトが肥大化し続ける。
NEARBY_CHARACTER_LIMIT = 20

NON_PERSON_PROBABILITY = 0.3
NON_PERSON_KINDS = ("国", "組織", "商会", "氏族", "集団", "物")

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

# 人物の筋書き(CharacterPlot)一件が結に至るまでの年数。生成時にこの範囲で引き、end に置く。
CHARACTER_PLOT_YEARS_RANGE = (1, 50)

MAX_CHARACTER_PLOT_PER_LOCATION = 5
