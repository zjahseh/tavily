import os
import logging
from dotenv import load_dotenv
from tavily import TavilyClient
import google.generativeai as genai
from googleapiclient.discovery import build
import gradio as gr
from datetime import date

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# ==========================
# 初始化環境變數
# ==========================
load_dotenv()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
CSE_ID = os.getenv("GOOGLE_CSE_ID")

if not (GOOGLE_API_KEY and CSE_ID and TAVILY_API_KEY):
    logging.warning("部分 API key / CSE ID 未設定。請確認 .env")

# 初始化客戶端（注意：依賴已安裝的套件）
tavily_client = TavilyClient(api_key=TAVILY_API_KEY) if TAVILY_API_KEY else None
try:
    genai.configure(api_key=GOOGLE_API_KEY)
    gemini_model = genai.GenerativeModel("models/gemini-2.5-flash") if GOOGLE_API_KEY else None
except Exception as e:
    logging.warning(f"Gemini 客戶端初始化失敗: {e}")
    gemini_model = None

# 初始化 Google Custom Search
search_service = None
if GOOGLE_API_KEY and CSE_ID:
    try:
        search_service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
    except Exception as e:
        logging.warning(f"Google CSE 初始化失敗: {e}")

# ==========================
# Phase 0: Google News 標題提取（容錯）
# ==========================
def get_google_news_headlines(max_results=15, query="台灣新聞"):
    headlines = []
    if not search_service:
        logging.warning("Google search service 未初始化，回傳預設分類")
        return ["台灣", "國際", "當地", "商業", "科學與科技", "娛樂", "體育", "健康"]

    try:
        # 注意：CSE 的 num 最大為 10
        res = search_service.cse().list(
            q=query,
            cx=CSE_ID,
            num=min(max_results, 10)
        ).execute()
        for item in res.get("items", []):
            title = item.get("title") or item.get("headline") or ""
            if title:
                headlines.append(title)
    except Exception as e:
        logging.error(f"❌ Google API 發生錯誤: {e}")
        return ["台灣", "國際", "當地", "商業", "科學與科技", "娛樂", "體育", "健康"]

    if not headlines:
        # 預設分類（避免後面流程被空列表打斷）
        return ["台灣", "國際", "當地", "商業", "科學與科技", "娛樂", "體育", "健康"]
    return headlines

# ==========================
# Phase 1: 探索事件（使用 Gemeni 做主題萃取）
# ==========================
def _safe_get_text_from_model_response(resp):
    """
    有些 client 會回傳不同結構：嘗試多種方式取得純文字
    """
    try:
        if resp is None:
            return ""
        # 可能是 dict-like
        if isinstance(resp, dict):
            # 常見 key
            for k in ("text", "content", "output"):
                if k in resp and isinstance(resp[k], str):
                    return resp[k]
            # 有時候 nested
            if "candidates" in resp and isinstance(resp["candidates"], list):
                for c in resp["candidates"]:
                    if isinstance(c, dict) and "content" in c:
                        return c["content"]
        # 物件可能有 text 屬性
        if hasattr(resp, "text"):
            return getattr(resp, "text") or ""
        if hasattr(resp, "content"):
            return getattr(resp, "content") or ""
        # fallback to str
        return str(resp)
    except Exception as e:
        logging.warning(f"model response parse fail: {e}")
        return ""

def get_main_events(query="今日新聞"):
    # 1) 取得初始標題列表
    news_titles = get_google_news_headlines(max_results=15, query=query)
    all_articles = []

    # 2) 用 Tavily 搜集每個子查詢的文章（time_range 使用 'w' 表示一週）
    if not tavily_client:
        logging.warning("Tavily client 未初始化，跳過深度抓取階段")
    else:
        for sub_query in news_titles:
            try:
                res = tavily_client.search(
                    query=sub_query,
                    max_results=15,
                    include_raw_content=True,
                    time_range="w"  # 使用 'w' (week)
                )
                results = res.get("results") if isinstance(res, dict) else getattr(res, "results", None)
                if results:
                    all_articles.extend(results)
            except Exception as e:
                logging.warning(f"⚠️ 子查詢失敗 ({sub_query})：{e}")

    # 將少量文章拼接成 context 提供給模型
    context_parts = []
    for a in all_articles[:40]:  # 上限避免 prompt 太長
        raw_content = a.get('raw_content') if isinstance(a, dict) else a.raw_content if hasattr(a, "raw_content") else ""
        title = a.get('title') if isinstance(a, dict) else a.title if hasattr(a, "title") else ""
        url = a.get('url') if isinstance(a, dict) else a.url if hasattr(a, "url") else ""
        safe_content = raw_content if isinstance(raw_content, str) else ""

        context_parts.append(
            f"來源: {url or '無'}\n"
            f"標題: {title or '無'}\n"
            f"內容: {safe_content[:800]}\n\n---\n\n"
        )

    context = "\n".join(context_parts) if context_parts else "無具體新聞內容（沒有抓到文章）"

    prompt = f"""
你是一位專業新聞編輯。
根據所有新聞，請幫我提煉出 3–5 個「熱門事件」，
每個主題只用四個字表示。
--- 開始新聞資料 ---
{context}
--- 結束新聞資料 ---
請每個主題獨立一行輸出，純文字，不要編號或其他符號。
"""

    # 若沒有 model，回傳簡單主題
    if not gemini_model:
        logging.warning("Gemini model 未初始化，回傳預設主題")
        return ["時事要聞", "國際動態", "經濟焦點"]

    try:
        raw_resp = gemini_model.generate_content(prompt)
        resp_text = _safe_get_text_from_model_response(raw_resp)
        # 清理回傳文字，確保每行都是 2~6 個中文字（方便你原先的四字需求）
        lines = [line.strip("•-–· 　 ").strip() for line in resp_text.splitlines() if line.strip()]
        # 過濾與截斷
        cleaned = []
        for ln in lines:
            ln = ln.replace("、", "").replace("，", "").strip()
            # 若超長，就只取前 4~8 個字（優先保留中文詞）
            if len(ln) > 8:
                ln = ln[:8]
            if ln:
                cleaned.append(ln)
        # 如果模型沒給，退回前面 headline 的前幾項
        if not cleaned:
            return news_titles[:5]
        return cleaned[:5]
    except Exception as e:
        logging.error(f"Gemini 生成失敗: {e}")
        return news_titles[:5]

# ==========================
# Phase 2: 深度搜尋文章（針對單一事件）
# ==========================
def get_event_articles(event):
    all_articles = []
    if not tavily_client:
        logging.warning("Tavily client 未初始化，無法深度搜尋")
        return []

    try:
        res = tavily_client.search(query=event, max_results=15, include_raw_content=True, time_range="d")  # d = day (24h)
        results = res.get("results") if isinstance(res, dict) else getattr(res, "results", None)
        if not results:
            return []
        for r in results:
            raw_content = r.get('raw_content') or ""
            url = r.get('url', "無網址")
            url_parts = url.split("/") if isinstance(url, str) else []
            source = url_parts[2] if len(url_parts) > 2 else r.get("source") or "未知來源"
            if raw_content:
                all_articles.append({
                    "source": source,
                    "title": r.get("title", "無標題"),
                    "url": url,
                    "content": raw_content
                })
        return all_articles
    except Exception as e:
        logging.warning(f"⚠️ 無法取得 {event} 的深度搜尋內容：{e}")
        return []

# ==========================
# Phase 3: 生成摘要（格式化 + 容錯）
# ==========================
def summarize_event(event, articles):
    if not articles:
        return f"⚠️ 警告：未找到關於「{event}」的有效新聞文章，無法生成摘要。"

    context_parts = []
    for art in articles[:10]:  # 取最多 10 篇做摘要來源
        content_text = art.get('content') or ""
        source_text = art.get('source', '未知來源')
        title_text = art.get('title', '無標題')
        context_parts.append(f"來源: {source_text}\n標題: {title_text}\n內容: {content_text[:750]}\n\n")
    context = "\n".join(context_parts)

    prompt = f"""
## 新聞報導多方觀點深度解析

請根據提供的多篇新聞報導資料，針對核心主題「{event}」進行全面分析與統整。

### 步驟一：報導內容綜合摘要
請首先客觀、簡潔地彙整所有報導的核心事實、時間線和主要涉及的人物或機構，形成一份綜合摘要。避免加入個人評論。

--- 報導資料 ---
{context}
--- 報導資料結束 ---

### 步驟二：核心對立觀點提煉與呈現
請識別並提煉出關於此事件的兩個最核心、最明確對立的觀點，並使用以下格式輸出：
=== 觀點一 ===
**核心主張：**
**主要論據（來自報導）：**
* ...
=== 觀點二 ===
**核心主張：**
**主要論據（來自報導）：**
* ...
"""
    if not gemini_model:
        logging.warning("Gemini model 未初始化，回傳簡單合成文字")
        # fallback 合成
        first_line = (articles[0].get("title") or "").strip()
        sample = f"（模型未初始化）綜合摘要範例：{first_line}"
        return sample

    try:
        raw_resp = gemini_model.generate_content(prompt)
        resp_text = _safe_get_text_from_model_response(raw_resp)
        return resp_text or f"（模型回傳為空）關於 {event} 的摘要無法取得"
    except Exception as e:
        logging.error(f"Gemini 摘要生成失敗: {e}")
        return f"⚠️ 模型生成失敗：{e}"

# ==========================
# Gradio helpers & UI 建構
# ==========================
def simplify_title(long_title, max_len=20):
    if not isinstance(long_title, str):
        return ""
    return long_title if len(long_title) <= max_len else long_title[:max_len] + "…"

def build_topics(limit=5):
    """
    延遲構建議題：避免在模組載入時做大量網路請求。
    """
    main_events = get_main_events()
    MOCK_TOPICS = []
    for event in main_events[:limit]:
        try:
            articles = get_event_articles(event)
            summary_text = summarize_event(event, articles)
            short_title = simplify_title(event)
            # 取整段文字的第一個非空行作為 sum（更穩健）
            first_line = next((ln for ln in summary_text.splitlines() if ln.strip()), "")
            MOCK_TOPICS.append({
                "full_title": event,
                "title": short_title,
                "heat": min(max(len(articles)//2 + 1, 1), 5),
                "sum": first_line,
                "summary": [{"source": a["source"], "text": a["content"][:500]} for a in articles],
                "url": [{"source": a["source"], "link": a["url"]} for a in articles]
            })
        except Exception as e:
            logging.warning(f"建立議題時發生錯誤 ({event})：{e}")
    # 若沒有任何議題，塞入預設
    if not MOCK_TOPICS:
        MOCK_TOPICS = [
            {"full_title":"時事要聞","title":"時事要聞","heat":3,"sum":"暫無資料","summary":[],"url":[]}
        ]
    return MOCK_TOPICS

# ---------- Gradio UI ----------
def create_gradio_app():
    MOCK_TOPICS = build_topics(limit=6)
    sorted_topics = sorted(MOCK_TOPICS, key=lambda x: x['heat'], reverse=True)

    with gr.Blocks(title="今日頭條生成器") as demo:
        # 分頁：列表 / 細節
        with gr.Column(visible=True, elem_id="topic_list_page") as list_page:
            gr.Markdown(f"## 📅 今日頭條議題 ({date.today().isoformat()})\n\n")
            topic_buttons = []
            for i, topic in enumerate(sorted_topics):
                # 每個按鈕顯示簡化過的標題
                topic_buttons.append(
                    gr.Button(f"{topic['title']}", visible=True, elem_id=f"topic_btn_{i}")
                )

        with gr.Column(visible=False, elem_id="topic_detail_page") as detail_page:
            # 返回按鈕（回傳顯示狀態）
            back_btn = gr.Button("← 返回議題列表", variant="secondary")
            back_btn.click(
                fn=lambda: (gr.update(visible=True), gr.update(visible=False)),
                outputs=[list_page, detail_page]
            )

            detail_title = gr.Markdown("## 議題標題")
            detail_summary = gr.Markdown("新聞摘要")
            detail_urls = gr.Markdown("參考新聞來源")

        # 點選後顯示細節的函式
        def go_to_detail(topic_index):
            # topic_index 為整數
            try:
                topic_data = sorted_topics[topic_index]
            except Exception:
                return (
                    gr.update(visible=True),
                    gr.update(visible=False),
                    "## 錯誤：找不到議題",
                    "此議題不存在或已過期。",
                    "### 🔗 無"
                )

            title_md = f"## 📰 {topic_data.get('full_title', '無標題')}"
            summary_parts = [f"### 💡 新聞摘要\n\n{topic_data.get('sum','暫無摘要')}\n"]
            summary_parts.append("### 🗞️ 各媒體觀點")
            for media_sum in topic_data.get('summary', []):
                source = media_sum.get('source', '未知來源')
                text = media_sum.get('text', '')
                summary_parts.append(f"\n**{source}：** {text}")
            full_summary_md = "\n".join(summary_parts)

            urls = topic_data.get('url', [])
            if not urls:
                urls_md = "### 🔗 參考新聞來源\n\n暫無來源"
            else:
                # 建立 markdown list
                urls_md = "### 🔗 參考新聞來源\n\n" + "\n".join(
                    f"* [{u.get('source','未知來源')}]({u.get('link','#')})" for u in urls
                )

            return (
                gr.update(visible=False),  # 隱藏列表
                gr.update(visible=True),   # 顯示細節頁
                title_md,
                full_summary_md,
                urls_md,
            )

        # 綁定按鈕（注意閉包問題，用預設參數固定 index）
        for i, btn in enumerate(topic_buttons):
            btn.click(
                fn=(lambda idx=i: go_to_detail(idx)),
                inputs=[],
                outputs=[list_page, detail_page, detail_title, detail_summary, detail_urls]
            )

    return demo

if __name__ == "__main__":
    app = create_gradio_app()
    # debug: 若要公開可設定 share=True（或 host/port）
    app.launch(server_name="0.0.0.0", server_port=7860, debug=False)
