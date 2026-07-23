"use client"

import { AnimatePresence, motion } from "framer-motion"
import { EASE } from "@/lib/motion"
import type { AvatarItem } from "@/lib/types"

interface AvatarDisplayProps {
  unlockedItems: AvatarItem[]
  mood?: string | null
}

// NEUTRAL・未知の値は意図的に含めない(グロー無し=何も分からない時の安全な既定値)
const MOOD_GLOW: Record<string, string> = {
  ANXIOUS: "#ffb84d",
  SAD: "#6ea8ff",
  FRUSTRATED: "#ff6b6b",
  HAPPY: "#b8935a",
}

/**
 * 会話の内容に応じて夜間睡眠サイクルが解除していく、志粋の全身コーデ。
 * unlockedItemsは解除日時の昇順で渡されるため、末尾(一番新しく解除したコーデ)
 * の全身画像1枚をそのまま表示する。何も解除していなければ素体(base.png)を表示する。
 * 各アイテムのassetは「小物の重ね着」ではなく、そのコーデを着た全身イラスト
 * そのものを指す(src/memory/avatar_catalog.pyがアイテム一覧の唯一の情報源)。
 *
 * moodは直近の会話から検知した感情の傾向(src/chat/emotion.py参照)。新しい
 * イラスト素材を必要としない軽量な視覚効果として、控えめなグローで表現する。
 */
export function AvatarDisplay({ unlockedItems, mood }: AvatarDisplayProps) {
  const currentOutfit = unlockedItems[unlockedItems.length - 1]
  const src = currentOutfit ? `/avatar/${currentOutfit.asset}` : "/avatar/base.png"
  const alt = currentOutfit?.display_name ?? ""
  const glowColor = mood ? MOOD_GLOW[mood] : undefined

  return (
    <div className="relative isolate h-full w-full">
      <AnimatePresence>
        {glowColor && (
          <motion.div
            key={mood}
            className="pointer-events-none absolute inset-0 -z-10 rounded-full"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.6, ease: EASE }}
            style={{ boxShadow: `0 0 48px 12px ${glowColor}66` }}
          />
        )}
      </AnimatePresence>
      <motion.div
        key={src}
        className="relative h-full w-full"
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.8, ease: EASE, delay: 0.5 }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src}
          alt={alt}
          className="absolute inset-0 h-full w-full object-cover object-top"
          style={{
            // 切り抜きの輪郭が背景から浮いて見える(MSペイントで貼り付けたような)
            // 問題への対応: 縁を放射状にフェードさせ、暗闇に自然に溶け込ませる。
            // mix-blend-modeは使わない(luminosityだとキャラクターの色自体が
            // 失われてしまうため、輪郭だけを馴染ませたい今回の目的には合わない)。
            maskImage: "radial-gradient(ellipse at center, black 55%, transparent 92%)",
            WebkitMaskImage: "radial-gradient(ellipse at center, black 55%, transparent 92%)",
          }}
        />
      </motion.div>
    </div>
  )
}
