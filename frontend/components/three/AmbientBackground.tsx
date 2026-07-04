"use client"

import { useMemo, useRef } from "react"
import { Canvas, useFrame } from "@react-three/fiber"
import * as THREE from "three"

const PARTICLE_COUNT = 400
const ACCENT_COLOR = "#c8ff00"

function Particles() {
  const pointsRef = useRef<THREE.Points>(null)

  const positions = useMemo(() => {
    const array = new Float32Array(PARTICLE_COUNT * 3)
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      array[i * 3] = (Math.random() - 0.5) * 18
      array[i * 3 + 1] = (Math.random() - 0.5) * 18
      array[i * 3 + 2] = (Math.random() - 0.5) * 10
    }
    return array
  }, [])

  // マウス追従はせず、常に一定のゆっくりした速度で回転させるだけに留める
  // (チャットの読みやすさを妨げない、環境音的なアニメーションにするため)
  useFrame((_, delta) => {
    if (!pointsRef.current) return
    pointsRef.current.rotation.y += delta * 0.02
    pointsRef.current.rotation.x += delta * 0.005
  })

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        color={ACCENT_COLOR}
        size={0.03}
        transparent
        opacity={0.35}
        sizeAttenuation
      />
    </points>
  )
}

function DriftingWireframe() {
  const meshRef = useRef<THREE.Mesh>(null)

  useFrame((_, delta) => {
    if (!meshRef.current) return
    meshRef.current.rotation.y += delta * 0.04
    meshRef.current.rotation.x += delta * 0.015
  })

  return (
    <mesh ref={meshRef} position={[0, 0, -4]}>
      <icosahedronGeometry args={[3, 0]} />
      <meshBasicMaterial color={ACCENT_COLOR} wireframe transparent opacity={0.08} />
    </mesh>
  )
}

/**
 * ヒーロー画面の背後に敷く、常時ゆっくり動くだけの環境的な3D背景。
 * マウス・スクロールには一切反応させない(チャットの操作性を妨げないため)。
 * dprを1.5に制限し、パーティクル数も抑えめにしてモバイルでの負荷を軽減している。
 */
export function AmbientBackground() {
  return (
    <div className="pointer-events-none absolute inset-0" aria-hidden="true">
      <Canvas
        dpr={[1, 1.5]}
        camera={{ position: [0, 0, 8], fov: 50 }}
        gl={{ antialias: true, alpha: true }}
      >
        <Particles />
        <DriftingWireframe />
      </Canvas>
    </div>
  )
}
