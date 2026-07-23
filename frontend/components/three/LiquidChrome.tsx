"use client"

import { useRef } from "react"
import { Canvas, useFrame } from "@react-three/fiber"
import { MeshDistortMaterial } from "@react-three/drei"
import * as THREE from "three"
import { usePointerRef } from "./usePointer"

/**
 * 「液体金属(リキッドクローム)」の装飾ブロブ。溶けた水銀/プラチナのような
 * 質感を、マウス位置に追従しながら常時ゆるやかに有機的な形状変化(distort)
 * させる。MeshDistortMaterial(@react-three/drei)はmetalness/roughness/
 * distort/speedを持つ既製のマテリアルで、手書きのGLSLシェーダーより
 * 見た目の予測がしやすい(私自身はレンダリング結果を目視できないため、
 * 実績のある既製コンポーネントを使うことでリスクを下げている)。
 *
 * 反射用にEnvironment(drei、実在の都市風景HDRI)を使っていたが、実際の
 * レンダリング結果を見ると「関係ない街並みが写り込んでいて違和感がある」
 * との指摘を受けた。写真的な環境マップはやめ、サイト自体のアクセントカラー
 * (アンバー+ダークブルー)だけを反射させる、色付きライトのみの構成に変更
 * (世界観を実写ではなくサイトの配色に合わせる)。
 */
function ChromeBlob({ pointer }: { pointer: React.RefObject<{ x: number; y: number }> }) {
  const meshRef = useRef<THREE.Mesh>(null)

  useFrame((_, delta) => {
    if (!meshRef.current) return
    meshRef.current.rotation.y += delta * 0.12
    meshRef.current.rotation.x += delta * 0.04
    const targetX = pointer.current.x * 0.5
    const targetY = -pointer.current.y * 0.5
    meshRef.current.position.x += (targetX - meshRef.current.position.x) * delta * 1.2
    meshRef.current.position.y += (targetY - meshRef.current.position.y) * delta * 1.2
  })

  return (
    <mesh ref={meshRef}>
      <sphereGeometry args={[1.3, 64, 64]} />
      <MeshDistortMaterial
        color="#0a0a0a"
        metalness={1}
        roughness={0.05}
        distort={0.45}
        speed={1.8}
      />
    </mesh>
  )
}

export function LiquidChrome({ className }: { className?: string }) {
  const pointer = usePointerRef()

  return (
    <div
      className={`pointer-events-none absolute ${className ?? ""}`}
      aria-hidden="true"
    >
      <Canvas
        dpr={[1, 1.5]}
        camera={{ position: [0, 0, 5], fov: 40 }}
        gl={{ antialias: true, alpha: true }}
      >
        <ambientLight intensity={0.15} />
        {/* サイトのアクセントカラー(アンバー)をキーライトに、ダークブルーを
            リムライトにして、金属面に「サイトの色」だけが映り込むようにする */}
        <pointLight position={[3, 2, 4]} intensity={3} color="#b8935a" />
        <pointLight position={[-3, -1, 2]} intensity={2} color="#5b7a9e" />
        <pointLight position={[0, 3, -2]} intensity={1.5} color="#ffffff" />
        <ChromeBlob pointer={pointer} />
      </Canvas>
    </div>
  )
}
