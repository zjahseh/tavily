import os
import logging
import requests
import feedparser
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from tavily import TavilyClient
import google.generativeai as genai
import gradio as gr
from datetime import date
from typing import List, Dict, Any

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# ==========================
# 初始化環境變數與客戶端
# ==========================
load_dotenv()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not (GOOGLE_API_KEY and TAVILY_API_KEY):
    logging.warning("⚠️ API key 未設定完整，請確認 .env (需 GOOGLE_API_KEY 與 TAVILY_API_KEY)")

# 初始化 Tavily
tavily_client = TavilyClient(api_key=TAVILY_API_KEY) if TAVILY_API_KEY else None

# 初始化 Gemini
gemini_model = None
try:
    if GOOGLE_API_KEY:
        genai.configure(api_key=GOOGLE_API_KEY)
        # 使用 gemini-1.5-flash
        gemini_model = genai.GenerativeModel("models/gemini-2.5-flash")
except Exception as e:
    logging.warning(f"Gemini 客戶端初始化失敗: {e}")

# ==========================
# RSS 邏輯 (源自 rss.py)
# ==========================
RSS_URL = "https://news.google.com/rss?hl=zh-TW&gl=TW"


def fetch_and_parse_rss(url: str):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        return feed
    except Exception as e:
        logging.error(f"RSS 抓取失敗: {e}")
        return None


def extract_links_from_description(html_content: str) -> List[str]:
    if not html_content:
        return []
    soup = BeautifulSoup(html_content, 'html.parser')
    links = []
    for link_tag in soup.find_all('a'):
        href = link_tag.get('href')
        if href and href not in links:
            links.append(href)
    return links


def get_rss_topics(max_items: int = 10) -> List[Dict[str, Any]]:
    """
    從 RSS 取得標題與相關連結
    """
    feed_data = fetch_and_parse_rss(RSS_URL)
    if not feed_data or not feed_data.entries:
        logging.warning("RSS 無資料，回傳預設列表")
        return []

    topics_list: List[Dict[str, Any]] = []

    for i, entry in enumerate(feed_data.entries):
        if i >= max_items:
            break

        all_links_set = set()
        all_links_set.add(entry.link)

        if hasattr(entry, 'description'):
            desc_links = extract_links_from_description(entry.description)
            all_links_set.update(desc_links)

        topics_list.append({
            'title': entry.title,
            'links': list(all_links_set)
        })

    return topics_list


# ==========================
# AI 處理邏輯 (整合 test.py)
# ==========================

def _safe_get_text(resp):
    try:
        if hasattr(resp, "text"): return resp.text
        if isinstance(resp, dict) and "content" in resp: return resp["content"]
        return str(resp)
    except:
        return ""


def get_articles_content(query_title, known_links=None):
    """
    使用 Tavily 針對 RSS 標題進行搜尋以獲取內文。
    """
    if not tavily_client:
        return []

    try:
        # 使用標題進行搜尋，獲取最新且相關的報導內文
        res = tavily_client.search(
            query=query_title,
            max_results=5,
            include_raw_content=True,
            time_range="week"
        )
        results = res.get("results", [])
        return results
    except Exception as e:
        logging.error(f"Tavily 搜尋失敗 ({query_title}): {e}")
        return []


def generate_analysis(topic_title, articles):
    """
    使用 Gemini 生成摘要與觀點分析
    """
    if not articles:
        return "⚠️ 無法取得相關新聞內容，請稍後再試。"

    # 組合 Prompt Context
    context_parts = []
    for art in articles:
        title = art.get('title', '無標題')
        content = art.get('content') or art.get('raw_content') or ""
        source = art.get('source', '未知來源')
        context_parts.append(f"來源: {source}\n標題: {title}\n內容: {content[:1000]}\n")

    context_str = "\n---\n".join(context_parts)

    prompt = f"""
你是一位精闢的新聞輿情分析師。你的任務是分析關於「{topic_title}」的多篇報導，
    重點在於找出「意見衝突」以及各方媒體的「鮮明立場」。

請嚴格按照以下 markdown 格式輸出，不要包含其他開場白：

### 📝 綜合摘要
(事件客觀懶人包 (約 150 字)，讓讀者一眼看懂發生什麼事。)

### 💥 核心衝突
(用一句話點出這個事件最大的爭議點或矛盾點是什麼？)

### ⚖️ 核心觀點對照
(列出事件中對立的觀點 (例如：支持方 vs 反對方，或是 樂觀派 vs 悲觀派)。)
       每個觀點包含：
       - 立場標籤
       - 他們的主要論述是什麼？
       - 哪幾篇報導或媒體持此觀點？


--- 報導資料 ---
{context_str}
"""
    if not gemini_model:
        return "⚠️ Gemini 模型未設定，無法生成摘要。"

    try:
        resp = gemini_model.generate_content(prompt)
        return _safe_get_text(resp)
    except Exception as e:
        return f"⚠️ 生成過程發生錯誤: {e}"


# ==========================
# Gradio UI (修正版)
# ==========================

def create_ui():
    # 1. 啟動時先抓取 RSS 列表 (快速)
    rss_topics = get_rss_topics(max_items=8)
    if not rss_topics:
        rss_topics = [{"title": "暫無新聞資料", "links": []}]

    # === 修改處：移除了 css 參數 ===
    with gr.Blocks(title="AI 新聞聚合器") as demo:

        gr.Markdown(f"## 📰 今日新聞聚合 ({date.today().isoformat()})")
        gr.Markdown("點擊左側議題，右側將即時生成 AI 分析摘要。")

        with gr.Row():
            # 左側：議題列表
            with gr.Column(scale=1, min_width=300):
                gr.Markdown("### 📌 熱門議題")
                btn_list = []
                # 動態生成按鈕
                for topic in rss_topics:
                    # 簡化標題顯示
                    display_title = topic['title'].split(' - ')[0]
                    btn = gr.Button(display_title, size="sm", variant="secondary")
                    btn_list.append((btn, topic['title']))

            # 右側：詳細內容
            with gr.Column(scale=2):
                header_display = gr.Markdown("### 👈 請點擊左側新聞議題")
                analysis_display = gr.Markdown("")
                loading_msg = gr.Markdown("", visible=False)

        # 處理點擊事件的函數
        def on_click(full_title):
            yield f"### 🔄 正在分析：{full_title}...", "⏳ 正在搜尋報導並進行 AI 歸納，請稍候...", gr.update(visible=True)

            # 1. 爬取內容
            articles = get_articles_content(full_title)

            # 2. 生成摘要
            analysis_text = generate_analysis(full_title, articles)

            # 3. 回傳結果
            yield f"### 📰 {full_title}", analysis_text, gr.update(visible=False)

        # 綁定事件
        for btn, full_title in btn_list:
            btn.click(
                fn=on_click,
                inputs=[gr.State(full_title)],
                outputs=[header_display, analysis_display, loading_msg]
            )

    return demo


if __name__ == "__main__":
    app = create_ui()
    app.launch(server_name="0.0.0.0", server_port=7860)
