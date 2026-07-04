"""育つアバターの解除可能アイテム一覧。

夜間睡眠サイクル(src/memory/sleep.py)が、その日の会話テーマを踏まえて
ここに定義したtheme_hintを手がかりにどのアイテムを解除するかLLMに判定させる。
実際のイラスト素材が用意でき次第、assetフィールド(frontend/public/avatar/配下の
ファイル名)を差し替えるだけで見た目を更新できる。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AvatarItem:
    slug: str
    display_name: str
    theme_hint: str  # LLM判定プロンプトで「どんな会話なら解除すべきか」を説明する
    asset: str  # frontend/public/avatar/配下のファイル名


AVATAR_CATALOG: list[AvatarItem] = [
    AvatarItem(
        slug="bookish_glasses",
        display_name="読書メガネ",
        theme_hint="文学・読書・本・作家についての話題が出た",
        asset="bookish_glasses.svg",
    ),
    AvatarItem(
        slug="chef_hat",
        display_name="シェフ帽",
        theme_hint="料理・食べ物・レシピについての話題が出た",
        asset="chef_hat.svg",
    ),
    AvatarItem(
        slug="study_lamp",
        display_name="勉強ランプ",
        theme_hint="勉強・受験・学習・試験についての話題が出た",
        asset="study_lamp.svg",
    ),
    AvatarItem(
        slug="music_headphones",
        display_name="ヘッドホン",
        theme_hint="音楽・アーティスト・曲についての話題が出た",
        asset="music_headphones.svg",
    ),
    AvatarItem(
        slug="travel_scarf",
        display_name="旅のマフラー",
        theme_hint="旅行・知らない場所・遠出についての話題が出た",
        asset="travel_scarf.svg",
    ),
    AvatarItem(
        slug="code_badge",
        display_name="コーダーバッジ",
        theme_hint="プログラミング・技術・開発についての話題が出た",
        asset="code_badge.svg",
    ),
]
