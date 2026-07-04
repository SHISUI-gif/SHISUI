"use client"

import { motion } from "framer-motion"
import { EASE } from "@/lib/motion"
import type { AvatarItem } from "@/lib/types"

interface AvatarDisplayProps {
  unlockedItems: AvatarItem[]
}

/**
 * 会話の内容に応じて夜間睡眠サイクルが解除していくアバター。
 * ベース(素体)は常に表示し、解除済みアイテムをその上に重ねて表示する。
 * 現時点ではプレースホルダーのSVG(frontend/public/avatar/配下)を使っており、
 * 実イラストが用意でき次第、同じファイル名で差し替えるだけで見た目が更新される
 * (src/memory/avatar_catalog.pyがアイテム一覧の唯一の情報源)。
 */
export function AvatarDisplay({ unlockedItems }: AvatarDisplayProps) {
  return (
    <motion.div
      className="relative h-32 w-32 sm:h-40 sm:w-40"
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.8, ease: EASE, delay: 0.5 }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/avatar/base.svg" alt="" className="absolute inset-0 h-full w-full" />
      {unlockedItems.map((item) => (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          key={item.slug}
          src={`/avatar/${item.asset}`}
          alt={item.display_name}
          className="absolute inset-0 h-full w-full"
        />
      ))}
    </motion.div>
  )
}
