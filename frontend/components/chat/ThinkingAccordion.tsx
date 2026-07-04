import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"

interface ThinkingAccordionProps {
  thinking: string
}

/**
 * 志粋の推論過程を、既定で閉じたアコーディオンとして表示する。
 * defaultValueを指定しないことで「既定で閉じた状態」を実現している。
 */
export function ThinkingAccordion({ thinking }: ThinkingAccordionProps) {
  if (!thinking.trim()) return null

  return (
    <Accordion type="single" collapsible className="mb-2 w-full max-w-full">
      <AccordionItem value="thinking" className="border-none">
        <AccordionTrigger className="py-1 text-[10px] font-mono tracking-wider text-white/30 uppercase hover:no-underline hover:text-[#c8ff00]/70">
          思考中...
        </AccordionTrigger>
        <AccordionContent className="text-xs text-white/25 whitespace-pre-wrap font-mono leading-relaxed">
          {thinking}
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  )
}
