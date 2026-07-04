"use client"

import { useEffect, useMemo, useRef } from "react"
import { Canvas, useFrame } from "@react-three/fiber"
import * as THREE from "three"

const PARTICLE_COUNT = 400
const ACCENT_COLOR = "#c8ff00"

/**
 * ポインター位置を[-1, 1]範囲に正規化してrefに保持するだけの購読フック。
 * pointer-events-noneなCanvas自体では拾えないため、windowで直接listenする。
 * ヒーロー画面限定で使うことを前提にしている(チャット画面ではこの
 * コンポーネント自体をマウントしない)。
 */
function usePointerRef() {
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

function Particles({ pointer }: { pointer: React.RefObject<{ x: number; y: number }> }) {
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

  // 常に一定のゆっくりした速度で回転させつつ、ポインター位置にごくわずかに
  // 視差で追従させる(チャット画面には出さないヒーロー限定の演出のため、
  // 読みやすさを妨げる心配が無い)。
  useFrame((_, delta) => {
    if (!pointsRef.current) return
    pointsRef.current.rotation.y += delta * 0.02
    pointsRef.current.rotation.x += delta * 0.005
    // ポインター位置へごく控えめに視差でずれる(位置のみ、回転速度自体は変えない)
    const targetX = pointer.current.x * 0.4
    const targetY = -pointer.current.y * 0.4
    pointsRef.current.position.x += (targetX - pointsRef.current.position.x) * delta * 1.5
    pointsRef.current.position.y += (targetY - pointsRef.current.position.y) * delta * 1.5
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

function DriftingWireframe({ pointer }: { pointer: React.RefObject<{ x: number; y: number }> }) {
  const meshRef = useRef<THREE.Mesh>(null)

  useFrame((_, delta) => {
    if (!meshRef.current) return
    meshRef.current.rotation.y += delta * 0.04
    meshRef.current.rotation.x += delta * 0.015
    // ポインターに向かってごく控えめに傾く(視差)。回転速度そのものは変えず、
    // 微小なオフセットを別軸に足すだけに留めて環境音的な性質を保つ。
    const targetTiltX = pointer.current.y * 0.12
    const targetTiltZ = pointer.current.x * -0.12
    meshRef.current.rotation.z += (targetTiltZ - meshRef.current.rotation.z) * delta * 1.2
    meshRef.current.position.y += (targetTiltX * 0.3 - meshRef.current.position.y) * delta * 1.2
  })

  return (
    <mesh ref={meshRef} position={[0, 0, -4]}>
      <icosahedronGeometry args={[3, 0]} />
      <meshBasicMaterial color={ACCENT_COLOR} wireframe transparent opacity={0.08} />
    </mesh>
  )
}

/**
 * ヒーロー画面の背後に敷く、常時ゆっくり動く環境的な3D背景。
 * 基本の回転は一定速度のままで、そこにポインター位置へのごくわずかな
 * 視差(パララックス)を上乗せする。チャット画面ではマウントされない
 * ヒーロー専用コンポーネントなので、チャットの操作性には影響しない。
 * dprを1.5に制限し、パーティクル数も抑えめにしてモバイルでの負荷を軽減している。
 */
export function AmbientBackground() {
  const pointer = usePointerRef()

  return (
    <div className="pointer-events-none absolute inset-0" aria-hidden="true">
      <Canvas
        dpr={[1, 1.5]}
        camera={{ position: [0, 0, 8], fov: 50 }}
        gl={{ antialias: true, alpha: true }}
      >
        <Particles pointer={pointer} />
        <DriftingWireframe pointer={pointer} />
      </Canvas>
    </div>
  )
}
