/**
 * 全画面に薄く重ねる粒状のノイズテクスチャ。近未来的な質感を出すための演出で、
 * 画像を一切使わずSVGのfeTurbulenceでその場生成するため、読み込みコストが
 * ほぼゼロ(base64画像を敷き詰めるより軽い)。操作を一切妨げないよう
 * pointer-events:noneにし、ごく薄いopacityに留めて情報の視認性を損なわない。
 */
export function GrainOverlay() {
  return (
    // mix-blend-modeは意図的に一切使わない: (1) iOS Safariはposition:fixed要素を
    // 別レイヤー(UIKitの独立したスクロールレイヤー)で合成するため、fixed要素や
    // その子にmix-blend-modeを付けると背景と正しく混合されないことがある。
    // (2) このオーバーレイはAmbientBackground.tsxのWebGL <canvas> の真上に
    // 常時重なるが、mix-blend-modeとGPU合成されるcanvasの組み合わせは
    // ブラウザ間で挙動が割れる既知の相互運用性ハザード。opacity-[0.05]の
    // ごく薄いノイズはnormal合成のままでも黒背景上で十分「粒状の質感」に
    // 見えるため、blend-modeを使わずに済ませるのが最も安全。
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 z-[9999]">
      <svg className="absolute inset-0 h-full w-full opacity-[0.08]">
        {/*
          color-interpolation-filters="sRGB" は明示必須: SVGフィルタの既定値は
          仕様上linearRGBで、feTurbulence/feColorMatrixの組み合わせは
          ブラウザごとにlinearRGB⇔sRGB変換の実装差が大きく、同じ値でも
          実効アルファ(不透明度)が数倍にずれることがある既知の相互運用性
          問題(特にWebKit)。ここで明示的にsRGB空間に固定し、opacity-[0.05]
          で意図した「ごく薄いノイズ」がブラウザ間で一定になるようにする。
        */}
        <filter id="shisui-grain" colorInterpolationFilters="sRGB">
          <feTurbulence
            type="fractalNoise"
            baseFrequency="0.85"
            numOctaves={2}
            stitchTiles="stitch"
            colorInterpolationFilters="sRGB"
          />
          {/*
            RGB出力はfeTurbulence自身のR/G/Bチャンネルの平均(0.33ずつ)にする —
            固定の白(1,1,1)にはしない。以前は常に白へ寄せていたため、blend-mode
            なしでも/ありでも中間輝度がニュートラルにならず、白い服やハイライトを
            含むアバターのような明るい被写体だけが不自然に薄まって見える原因になっていた。
          */}
          <feColorMatrix
            type="matrix"
            values="0.33 0.33 0.33 0 0  0.33 0.33 0.33 0 0  0.33 0.33 0.33 0 0  0 0 0 0.9 0"
            colorInterpolationFilters="sRGB"
          />
        </filter>
        <rect width="100%" height="100%" filter="url(#shisui-grain)" />
      </svg>
    </div>
  )
}
