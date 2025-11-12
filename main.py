# 📦 自動新聞整合系統 v1.1
# 功能：整合 Google Custom Search + Tavily 搜尋 + Gemini 摘要 → 生成台灣每日新聞綜合報告

import os
from dotenv import load_dotenv
from tavily import TavilyClient
import google.generativeai as genai
import pandas as pd
import time
from google.generativeai import types
from googleapiclient.discovery import build

# ==========================
# 初始化環境變數
# ==========================
load_dotenv()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")  # 你的 API Key
CSE_ID = os.getenv("GOOGLE_CSE_ID")           # Google Custom Search Engine ID

if not TAVILY_API_KEY or not GOOGLE_API_KEY or not CSE_ID:
    raise ValueError("❌ 請確認已在 .env 檔中設定 TAVILY_API_KEY、GOOGLE_API_KEY 與 GOOGLE_CSE_ID")

# 初始化客戶端
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
genai.configure(api_key=GOOGLE_API_KEY)
gemini_model = genai.GenerativeModel("models/gemini-2.5-flash")

# 初始化 Google Custom Search
search_service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)


# ==========================
# Phase 0：Google News 標題提取 (API 版)
# ==========================
def get_google_news_headlines(max_results=15, query="台灣新聞"):
    """
    使用 Google Custom Search API 取得新聞標題
    """
    print("📰 [Phase 0] 透過 Google Custom Search API 獲取新聞標題...")

    headlines = []
    try:
        res = search_service.cse().list(
            q=query,
            cx=CSE_ID,
            num=min(max_results, 10),  # API 限制一次最多 10
            lr='lang_zh'
        ).execute()

        for item in res.get("items", []):
            headlines.append(item.get("title"))

        if headlines:
            print(f"✅ 成功獲取 {len(headlines)} 個 Google News 標題")
            return headlines
        else:
            print("⚠️ API 回傳內容為空，使用靜態備援")
            return [ "台灣","國際","當地","商業","科學與科技","娛樂","體育","健康"

        ]

    except Exception as e:
        print(f"❌ Google API 發生錯誤: {e}")
        return [    "台灣","國際","當地","商業","科學與科技","娛樂","體育","健康"
        ]


# ==========================
# Phase 1：探索事件 (使用 Google News 標題)
# ==========================
def get_main_events(query="今日新聞"):
    news_titles = get_google_news_headlines(max_results=15, query=query)

    sub_queries = news_titles
    print(f"🔍 [Phase 1] 搜尋 (使用 {len(news_titles)} 個 Google News 標題) 中...")

    all_articles = []
    for sub_query in sub_queries:
        try:
            response = tavily_client.search(
                query=sub_query,
                max_results=15,
                include_raw_content=True,
                time_range="week"
            )
            all_articles.extend(response["results"])
        except Exception as e:
            print(f"⚠️ 子查詢失敗 ({sub_query})：{e}")

    context = ""
    for a in all_articles:
        raw_content = a.get('raw_content') or ''
        context += f"來源: {a.get('url', '無')}\n標題: {a.get('title', '無')}\n內容: {raw_content[:1000]}\n\n---\n\n"

    prompt = f"""
    你是一位專業新聞編輯。
    根據所有新聞，請幫我提煉出 3–5 個「熱門事件」，
    每個主題以一句簡短文字表示。
    --- 開始新聞資料 ---
    {context}
    --- 結束新聞資料 ---
    """
    response = gemini_model.generate_content(prompt)
    print("✅ 主題提取完成\n")
    return [e.strip("•").strip() for e in response.text.split("\n") if e.strip()]


# ==========================
# Phase 2–4 保持原本程式不變
# ==========================
def get_event_articles(event):
    print(f"📰 [Phase 2] 深度搜尋：{event}")
    all_articles = []

    try:
        res = tavily_client.search(query=event, max_results=15, include_raw_content=True, time_range="day")
        for r in res["results"]:
            raw_content = r.get("raw_content") or ""
            url_parts = r.get("url", "無網址").split("/")
            source = url_parts[2] if len(url_parts) > 2 else "未知來源"
            if raw_content:
                all_articles.append({
                    "source": source,
                    "title": r.get("title", "無標題"),
                    "url": r.get("url", "無網址"),
                    "content": raw_content
                })
        return all_articles

    except Exception as e:
        print(f"⚠️ 無法取得 {event} 的深度搜尋內容：{e}")
        return []


def summarize_event(event, articles):
    print(f"🧠 [Phase 3] 摘要整合：{event}")
    if not articles:
        return f"⚠️ 警告：未找到關於「{event}」的有效新聞文章，無法生成摘要。"

    context = ""
    for art in articles:
        content_text = art.get('content') or ""
        source_text = art.get('source', '未知來源')
        title_text = art.get('title', '無標題')
        context += f"來源: {source_text}\n標題: {title_text}\n內容: {content_text[:750]}\n\n"

    prompt = f"""
    以下是關於「{event}」的多家新聞報導。
    請幫我綜合這些內容，撰寫約 500 字的客觀摘要，
    需包含主要事實與各媒體的不同觀點。

    --- 報導資料 ---
    {context}
    --- 結束 ---
    """
    response = gemini_model.generate_content(prompt)
    return response.text


def generate_news_report():
    main_events = get_main_events()
    report = {}

    for event in main_events[:5]:
        articles = get_event_articles(event)
        if not articles:
            continue
        summary = summarize_event(event, articles)
        report[event] = summary

    print("\n==================== 🗞️ 今日綜合新聞摘要 ====================")
    for topic, summary in report.items():
        print(f"\n🟦 {topic}\n{summary}\n{'-' * 60}")
    print("==============================================================")


# ==========================
# 主程式入口
# ==========================
if __name__ == "__main__":
    generate_news_report()
