"use client"

import { useId } from "react"

/**
 * ぼかした色付きの光の玉+粒状のフィルムグレイン質感をセットにした背景装飾。
 * ユーザーが繰り返し参考にした外部UI(暖色のぼかし写真+粒感テクスチャ)の
 * 「なめらかなCSS blurだけでは質感が足りない」という指摘を受けて、
 * GrainOverlay.tsx(全画面のごく薄いノイズ)とは別に、この光の玉の範囲だけ
 * 粒感を強めに重ねる。mix-blend-modeは使わない
 * (position:fixedとの組み合わせでiOS Safariが正しく合成しないバグが
 * 既知のため、GrainOverlay.tsxと同じ理由でここでも避け、通常合成のまま
 * オパシティで質感を出す)。
 *
 * classNameで大きさ・位置・色・opacityを指定する(例: "h-2/3 w-2/3 -right-1/3
 * -top-1/3 bg-[#b8935a]/[0.10]")。className内の背景色クラスがそのまま
 * ぼかしの色になるため、サイト全体のアクセント色が変わってもこの
 * コンポーネント自体を書き換える必要はない。
 */
export function GlowBlob({ className }: { className: string }) {
  const filterId = useId()

  return (
    <div aria-hidden="true" className={`pointer-events-none absolute overflow-hidden rounded-full ${className}`}>
      <div className="absolute inset-0 rounded-full blur-[90px]" style={{ background: "inherit" }} />
      <svg className="absolute inset-0 h-full w-full opacity-[0.5]">
        <filter id={filterId} colorInterpolationFilters="sRGB">
          <feTurbulence
            type="fractalNoise"
            baseFrequency="0.9"
            numOctaves={2}
            stitchTiles="stitch"
            colorInterpolationFilters="sRGB"
          />
          <feColorMatrix
            type="matrix"
            values="0.33 0.33 0.33 0 0  0.33 0.33 0.33 0 0  0.33 0.33 0.33 0 0  0 0 0 0.6 0"
            colorInterpolationFilters="sRGB"
          />
        </filter>
        <rect width="100%" height="100%" filter={`url(#${filterId})`} />
      </svg>
    </div>
  )
}
