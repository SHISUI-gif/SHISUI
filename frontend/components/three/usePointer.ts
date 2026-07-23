"use client"

import { useEffect, useRef } from "react"

/**
 * ポインター位置を[-1, 1]範囲に正規化してrefに保持するだけの購読フック。
 * pointer-events-noneなCanvas自体では拾えないため、windowで直接listenする。
 * AmbientBackground.tsx/LiquidChrome.tsxの両方で使う共通ロジックのため
 * 切り出している。
 */
export function usePointerRef() {
  const pointer = useRef({ x: 0, y: 0 })

  useEffect(() => {
    const handlePointerMove = (event: PointerEvent) => {
      pointer.current = {
        x: (event.clientX / window.innerWidth) * 2 - 1,
        y: (event.clientY / window.innerHeight) * 2 - 1,
      }
    }
    window.addEventListener("pointermove", handlePointerMove)
    return () => window.removeEventListener("pointermove", handlePointerMove)
  }, [])

  return pointer
}
