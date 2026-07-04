import threading

import gradio as gr
from gradio.themes.utils import colors, fonts

from src.chat.shisui_chat import stream_shisui_reply
from src.corpus.scheduler import maybe_run_daily_archive_crawl
from src.debate.scheduler import maybe_run_daily_debate_autonomous
from src.memory.scheduler import maybe_run_daily_sleep
from src.study.scheduler import maybe_run_daily_study


def chat_with_shisui(user_message, history):
    """
    家族のiPhoneや那由多のMacからの入力を受け取り、志粋の頭脳(src/chat/shisui_chat.py)へ流す関数。
    """
    yield from stream_shisui_reply(user_message, history)

# ✨ nuevo.tokyo(モノクローム×和のグラデーション×ミニマルな余白)を参考にしたデザイン。
# 「モノクローム」は強いコントラスト(純白/ほぼ黒)が肝なので中間グレーには寄せない。
# 「和のグラデーション」は常時見える場所(タイトル下のバー)に置き、操作しないと見えない
# ボタンのホバー色だけに頼らないようにする。
_AI_IRO = colors.Color(
    name="ai",
    c50="#eef3f8", c100="#d7e3ee", c200="#b0c7dd", c300="#89abcc",
    c400="#5686b0", c500="#2c5f8a", c600="#204a6d", c700="#193a56",
    c800="#132c42", c900="#0d1f2f", c950="#08141f",
)

SHISUI_THEME = gr.themes.Base(
    primary_hue=_AI_IRO,
    neutral_hue=colors.gray,
    font=[fonts.GoogleFont("IBM Plex Mono"), "ui-monospace", "monospace"],
    font_mono=[fonts.GoogleFont("IBM Plex Mono"), "ui-monospace", "monospace"],
).set(
    body_background_fill="#ffffff",
    body_background_fill_dark="#0a0a0a",
    background_fill_primary="#ffffff",
    background_fill_primary_dark="#0a0a0a",
    block_background_fill="#ffffff",
    block_background_fill_dark="#0a0a0a",
    block_border_width="1px",
    block_border_color="#e5e5e5",
    block_border_color_dark="#2a2a2a",
    block_shadow="none",
    block_radius="2px",
    body_text_color="#111111",
    body_text_color_dark="#f2f2f2",
    button_primary_background_fill="linear-gradient(120deg, #1f3c57 0%, #7a2e2e 100%)",
    button_primary_background_fill_hover="linear-gradient(120deg, #14293c 0%, #5c2222 100%)",
    button_primary_text_color="#ffffff",
    input_background_fill="#ffffff",
    input_background_fill_dark="#141414",
    input_border_color="#111111",
    input_border_color_dark="#f2f2f2",
)

# nuevo.tokyoの実物(白背景・モノスペース・技術文書調のコピー・角のあるグラデーションパネル)
# を踏まえたCSS。丸み・影・暖色の柔らかい余白は排除し、グリッド線と等幅フォントで統一する。
SHISUI_CSS = """
.gradio-container { max-width: 760px !important; margin: 0 auto !important; }
#shisui-title { border-bottom: 1px solid #111111; padding-bottom: 20px !important; margin-bottom: 24px !important; }
#shisui-title h1 {
    letter-spacing: 0.02em; font-weight: 600; font-size: 1.6rem !important;
    margin-bottom: 6px !important; text-transform: uppercase;
}
#shisui-title p { opacity: 0.5; letter-spacing: 0.01em; font-size: 0.85rem !important; margin: 0 !important; }
#shisui-title-bar {
    height: 40px; width: 100%; margin-top: 16px;
    background: linear-gradient(100deg, #1f3c57 0%, #b0c7dd 35%, #7a2e2e 70%, #1a1a1a 100%);
}
.message-wrap .message { border-radius: 0px !important; box-shadow: none !important; }
footer { display: none !important; }
"""

# 注意: Gradio 6.x以降、theme/cssはgr.Blocks()ではなくlaunch()に渡す仕様(過去に一度直した箇所)。
# 新しいgr.Blocks(...)呼び出しを追加するときは、必ずこのコメントを確認してlaunch()側に書くこと。
with gr.Blocks(title="自律型AI - 志粋 -") as demo:
    with gr.Column(elem_id="shisui-title"):
        gr.Markdown(
            """
            # 志粋 — SHISUI
            AUTONOMOUS LOCAL AI · 那由多のM5 Pro Macで稼働中
            """
        )
        gr.HTML('<div id="shisui-title-bar"></div>')

    # チャットUIの設置 (再生成/1つ戻る/クリアはGradio 6.xではChatbotに標準搭載されており個別指定は不要)
    gr.ChatInterface(
        fn=chat_with_shisui,
        textbox=gr.Textbox(placeholder="志粋にメッセージを送る...", container=False, scale=7),
    )

if __name__ == "__main__":
    # 記憶圧縮システム・青空文庫全体クロールは、ネットワークI/O(礼儀正しい待機)や
    # LLM呼び出しで数十秒〜数分かかることがあるため、Gradio起動をブロックしないよう
    # バックグラウンドスレッドで実行する(daemon=Trueなのでアプリ終了時に自動で片付く)
    threading.Thread(target=maybe_run_daily_sleep, daemon=True).start()
    threading.Thread(target=maybe_run_daily_archive_crawl, daemon=True).start()
    # 夜間修行・自律討論はlaunchd(launchctl load)の有効化を保留しているため、
    # launchdなしでも1日1回動くよう、他の日次ジョブと同じ仕組みに乗せる
    threading.Thread(target=maybe_run_daily_study, daemon=True).start()
    threading.Thread(target=maybe_run_daily_debate_autonomous, daemon=True).start()

    # ⚠️ 超重要:server_name="0.0.0.0" にすることで、同じWi-Fiにいる家族のiPhoneからアクセス可能になるよ!
    # share=True にすると、Tailscaleを使わなくても一時的な外部URL(72時間有効)を自動発行してくれるから、最初はこれも便利!
    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=True,
        theme=SHISUI_THEME,
        css=SHISUI_CSS,
    )
