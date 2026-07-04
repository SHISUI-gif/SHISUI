"use client"

import { motion } from "framer-motion"

const RAYS = [45, 135, 225, 315]

/**
 * メッセージ送信直後、まだ"thinking"も"content"も届いていない空白の間に表示する
 * パルスアニメーション。「何も起きていないわけではない、処理中だ」と伝えるための
 * ものなので、他の一度きりの演出と違ってここだけは無限ループで良い。
 */
export function PendingPulse() {
  return (
    <div className="flex h-10 w-10 items-center justify-center" role="status" aria-label="応答を生成中">
      <svg viewBox="0 0 100 100" className="h-10 w-10">
        {RAYS.map((angle) => (
          <motion.line
            key={angle}
            x1={50 + 14 * Math.cos((angle * Math.PI) / 180)}
            y1={50 + 14 * Math.sin((angle * Math.PI) / 180)}
            x2={50 + 24 * Math.cos((angle * Math.PI) / 180)}
            y2={50 + 24 * Math.sin((angle * Math.PI) / 180)}
            stroke="#c8ff00"
            strokeWidth={3}
            strokeLinecap="round"
            initial={{ opacity: 0.25 }}
            animate={{ opacity: [0.25, 1, 0.25] }}
            transition={{ duration: 1.2, repeat: Infinity, ease: "easeInOut" }}
          />
        ))}
        <motion.circle
          cx={50}
          cy={50}
          r={9}
          fill="#c8ff00"
          initial={{ scale: 0.9 }}
          animate={{ scale: [0.9, 1.08, 0.9] }}
          transition={{ duration: 1.2, repeat: Infinity, ease: "easeInOut" }}
        />
      </svg>
    </div>
  )
}
