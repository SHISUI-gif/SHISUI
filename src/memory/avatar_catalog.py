"""育つアバターの解除可能な全身コーデ一覧。

夜間睡眠サイクル(src/memory/sleep.py)が、その日の会話テーマを踏まえて
ここに定義したtheme_hintを手がかりにどのコーデを解除するかLLMに判定させる。
assetは小物の重ね着ではなく、そのコーデを着た志粋の全身イラストそのものを指す。
現在の素材はPollinations AI(無料・APIキー不要の画像生成API)で、同一seed値+
共通のキャラクター記述文(髪型・服装・配色)を使い回すことで、キャラクターの
一貫性を保ちながら生成したもの(生成手順は該当作業のスクラッチパッド参照)。
より高品質な本物のイラストが用意でき次第、assetフィールド
(frontend/public/avatar/配下のファイル名)を差し替えるだけで見た目を更新できる。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AvatarItem:
    slug: str
    display_name: str
    theme_hint: str  # LLM判定プロンプトで「どんな会話なら解除すべきか」を説明する
    asset: str  # frontend/public/avatar/配下のファイル名(そのコーデの全身画像)


AVATAR_CATALOG: list[AvatarItem] = [
    AvatarItem(
        slug="bookish_glasses",
        display_name="読書メガネ",
        theme_hint=(
            "文学・読書・本・作家についての話題に加え、小説・漫画・アニメ・映画の"
            "ストーリーや世界観について語る、知的好奇心をくすぐるような話題全般"
        ),
        asset="bookish_glasses.png",
    ),
    AvatarItem(
        slug="chef_hat",
        display_name="シェフ帽",
        theme_hint=(
            "料理・食べ物・レシピについての話題に加え、グルメ・お店・カフェ・"
            "お菓子・飲み物など「食」にまつわる話題全般"
        ),
        asset="chef_hat.png",
    ),
    AvatarItem(
        slug="study_lamp",
        display_name="勉強ランプ",
        theme_hint=(
            "勉強・受験・学習・試験についての話題に加え、資格・スキルアップ・"
            "何かを調べたり深く学ぼうとする話題全般(志粋自身の夜間修行や"
            "自己学習についての質問も含む)"
        ),
        asset="study_lamp.png",
    ),
    AvatarItem(
        slug="music_headphones",
        display_name="ヘッドホン",
        theme_hint=(
            "音楽・アーティスト・曲についての話題に加え、ライブ・カラオケ・"
            "ゲームなど、耳や音にまつわるエンタメ全般"
        ),
        asset="music_headphones.png",
    ),
    AvatarItem(
        slug="travel_scarf",
        display_name="旅のマフラー",
        theme_hint=(
            "旅行・知らない場所・遠出についての話題に加え、お出かけ・季節の"
            "イベントや祭り・行ってみたい場所についての話題全般"
        ),
        asset="travel_scarf.png",
    ),
    AvatarItem(
        slug="code_badge",
        display_name="コーダーバッジ",
        theme_hint=(
            "プログラミング・技術・開発についての話題に加え、AI・ガジェット・"
            "新機能・アプリなど、テクノロジー全般についての話題"
        ),
        asset="code_badge.png",
    ),
]
