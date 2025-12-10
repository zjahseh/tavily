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
import json
import typing_extensions as typing
from google.generativeai.types import HarmCategory, HarmBlockThreshold

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
        gemini_model = genai.GenerativeModel("models/gemini-2.5-flash")
except Exception as e:
    logging.warning(f"Gemini 客戶端初始化失敗: {e}")


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
        clean_query = query_title.split(' - ')[0] + " 新聞"

        # 使用標題進行搜尋，獲取最新且相關的報導內文
        res = tavily_client.search(
            query=clean_query,
            max_results=5,
            include_raw_content=True,
            time_range="week"
        )
        results = res.get("results", [])
        return results
    except Exception as e:
        logging.error(f"Tavily 搜尋失敗 ({query_title}): {e}")
        return []


class Perspective(typing.TypedDict):
    stance_label: str       # 立場標籤 (例如：支持方、樂觀派)
    argument: str           # 主要論述
    sources: list[str]      # 媒體來源列表

class NewsAnalysisResult(typing.TypedDict):
    summary: str            # 綜合摘要
    core_conflict: str      # 核心衝突點
    perspectives: list[Perspective] # 觀點列表

def generate_analysis(topic_title, articles):
    """
    使用 Gemini 生成摘要與觀點分析
    """
    if not articles:
        return "⚠️ 無法取得相關新聞內容，請檢查網路或 Tavily 設定。"
        
    if 'gemini_model' not in globals() or not gemini_model:
        return "⚠️ Gemini 模型未設定，無法生成摘要。"

    # 組合 Prompt Context
    context_parts = []
    for art in articles:
        title = art.get('title', '無標題')
        raw_c = art.get('raw_content') or art.get('content') or ""
        url = art.get('source') or art.get('url') or '#'
        context_parts.append(f"標題: {title}\n連結: {url}\n內文: {str(raw_c)[:600]}\n")

    print(f"Gemini context_parts: {context_parts}")
    context_str = "\n---\n".join(context_parts)
    print(f"Gemini context_str: {context_str}")
    
    prompt = f"""
    你是一位精闢的新聞輿情分析師。你的任務是分析關於「{topic_title}」的多篇報導。
        
    請以 JSON 格式輸出新聞分析。
    
    【重要規則】
    1. 絕對禁止重複語句：summary 必須精簡，若發現自己在重複同樣的詞彙 (如"共創"、"未來")，請立刻停止。
    2. sources 格式：在 perspectives 中，來源必須包含網址，請使用 Markdown 格式： `[媒體名稱](URL)`。
    3. 若新聞內容只有單方說法 (缺乏對立面)，請在 perspectives 中只列出該方觀點，不要硬湊反對方。
    
    【輸出欄位要求】
    1. summary (摘要): 繁體中文，控制在 150 字以內，不要廢話。
    2. core_conflict (核心衝突): 一句話描述。
    3. perspectives (觀點): 列出主要立場。
       - stance_label: 立場 (如: 支持方)
       - argument: 論點
       - sources: 來源列表，例如 ["[聯合報](https://...)", "[CNN](https://...)"]

    --- 新聞素材 ---
    {context_str}
    """

    # 新聞內容常涉及衝突，預設設定很容易誤殺
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    try:
        # 3. 設定 Generation Config 強制輸出 JSON
        response = gemini_model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=NewsAnalysisResult,
                temperature=0.4,    # 🔥 關鍵：降低創意度，減少鬼打牆機率
                top_p=0.9,          # 💡 調整：Top-P 取樣，幫助模型跳脫重複詞彙
                max_output_tokens=9000 # 🔥 關鍵：強制限制長度，避免生成過久
            )
        )

        # 5. 🔥 防崩潰檢查：確認是否真的有回傳文字
        if not response.parts:
            logging.error(f"Gemini 回傳空內容。Finish Reason: {response.candidates[0].finish_reason}")
            # 嘗試讀取 prompt feedback 看是否輸入有問題
            if response.prompt_feedback:
                logging.error(f"Prompt Feedback: {response.prompt_feedback}")
            return f"⚠️ 分析失敗：AI 未回傳任何內容 (原因代碼: {response.candidates[0].finish_reason})。可能因內容過於敏感或模型負載過高。"

        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        print(f"Gemini Raw Response: {clean_text}")

        # 5. 嘗試解析與自動修復
        try:
            data = json.loads(clean_text)
        except json.JSONDecodeError:
            # 🚑 急救機制：如果 JSON 斷尾，嘗試人工補全結構
            # 這能救回大部分 "話沒講完" 的情況
            logging.warning("JSON 截斷，嘗試自動修復...")
            try:
                # 假設斷在 list 或 object 中間，暴力補上結尾符號
                repaired_text = clean_text + '"}]}' 
                data = json.loads(repaired_text)
            except:
                # 真的沒救了，回傳原始文字讓使用者加減看
                return f"⚠️ 解析失敗 (JSON 截斷)。\n雖然 AI 沒寫完，但以下是它產生的部分內容：\n\n{clean_text}"
            
        
        # --- 開始組裝 Markdown ---
        md_output = f"""### 📝 綜合摘要
    {data.get('summary', '無摘要')}

    ### 💥 核心衝突
    {data.get('core_conflict', '無明顯衝突')}

    ### ⚖️ 核心觀點對照
    """
            
        # 遍歷觀點列表
        for p in data.get('perspectives', []):
            sources_str = ", ".join(p.get('sources', []))
            md_output += f"""
    - **【{p.get('stance_label', '觀點')}】**
    - 💬 **論點**：{p.get('argument', '無')}
    - 📰 **來源**：_{sources_str}_
    """
            
        return md_output

    except json.JSONDecodeError:
        return f"⚠️ 解析失敗，模型回傳了非 JSON 格式: {response.text}"
    except Exception as e:
        return f"⚠️ 生成過程發生錯誤: {e}"


# ==========================
# Gradio UI
# ==========================

def create_ui():
    # 1. 啟動時先抓取 RSS 列表 (快速)
    rss_topics = get_rss_topics(max_items=8)
    if not rss_topics:
        rss_topics = [{"title": "暫無新聞資料", "links": []}]

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
                outputs=[header_display, analysis_display, loading_msg],
                show_progress=False
            )

    return demo


if __name__ == "__main__":
    app = create_ui()
    app.launch(server_name="0.0.0.0", server_port=7860)
