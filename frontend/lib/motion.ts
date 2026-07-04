/**
 * サイト全体で使い回す、唯一のイージングカーブ・速度の定義。
 * 「差し色は1色・イージングは1種類だけ」という一貫性ルールを守るための共有定数。
 * ここ以外でアニメーションのdurationやeaseを直書きしない。
 */
export const EASE = [0.22, 1, 0.36, 1] as const // power3.out相当

export const DURATION = {
  fast: 0.2, // 小さなUI要素(ボタン、メッセージ1件など)
  base: 0.4, // ロゴ・見出しなど中サイズの要素
} as const
