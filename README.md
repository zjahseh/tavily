📰 AI News Aggregator & Analyzer (AI 新聞輿情分析平台)
這是一個基於 Python 的即時新聞聚合與分析工具。它結合了 Google News RSS、Tavily Search API 以及 Google Gemini Pro/Flash 模型，能自動抓取當日熱門議題，並透過 AI 生成深度摘要，分析事件的核心衝突與正反方觀點。

✨ 主要功能
⚡ 即時熱點聚合：自動抓取 Google News (台灣區) 的 RSS Feed，獲取當下最熱門的新聞議題。

🔍 深度內容檢索：利用 Tavily API 針對特定議題進行網路搜尋，抓取多篇相關報導的完整內文，不只看標題。

🤖 AI 輿情分析：

綜合摘要：過濾雜訊，生成 150 字內的客觀懶人包。

核心衝突識別：AI 自動判斷該事件最大的爭議點或矛盾點。

多元觀點對照：自動歸納「支持方 vs 反對方」或「樂觀派 vs 悲觀派」的論述，並附上媒體來源。

🖥️ 互動式 Web UI：使用 Gradio 建置的簡潔介面，點擊左側議題即可即時生成右側報告。

🛡️ 穩定的輸出格式：採用 JSON Schema 強制 Gemini 輸出結構化資料，並包含自動修復機制，防止 AI 生成內容截斷。

🛠️ 技術架構
UI 介面: Gradio

LLM 模型: Google Gemini (gemini-2.5-flash 或 1.5-flash)

搜尋引擎: Tavily Search API (用於 RAG 檢索)

資料來源: Feedparser (RSS)

爬蟲輔助: BeautifulSoup4, Requests

🚀 快速開始

1. 前置需求

請確保你已安裝 Python 3.10 或以上版本，並且擁有以下 API Key：

Google AI Studio Key: 用於存取 Gemini 模型 ([取得連結](https://aistudio.google.com/usage?timeRange=last-28-days&project=w6rag-475210))

Tavily API Key: 用於搜尋新聞內文 ([取得連結](https://www.tavily.com))

2. 安裝專案

# Clone 此專案
git clone https://github.com/your-username/ai-news-aggregator.git
cd ai-news-aggregator

# 建立虛擬環境 (建議)
python -m venv .venv
source .venv/bin/activate  # Mac/Linux
# .venv\Scripts\activate   # Windows

# 安裝依賴套件
pip install -r requirements.txt
   
3. 設定環境變數
   
在專案根目錄建立一個 .env 檔案，並填入你的 API Key：

# .env 檔案內容
GOOGLE_API_KEY=你的_Gemini_API_Key
TAVILY_API_KEY=你的_Tavily_API_Key

4. 啟動應用程式

python main.py

這是一份為你的專案量身打造的 README.md。我根據你的程式碼邏輯（Gradio 介面、Gemini 分析、Tavily 搜尋、RSS 聚合）撰寫了完整的功能介紹與安裝教學。

你可以直接複製以下內容到你的 GitHub 儲存庫中。

📰 AI News Aggregator & Analyzer (AI 新聞輿情分析平台)
這是一個基於 Python 的即時新聞聚合與分析工具。它結合了 Google News RSS、Tavily Search API 以及 Google Gemini Pro/Flash 模型，能自動抓取當日熱門議題，並透過 AI 生成深度摘要，分析事件的核心衝突與正反方觀點。

✨ 主要功能
⚡ 即時熱點聚合：自動抓取 Google News (台灣區) 的 RSS Feed，獲取當下最熱門的新聞議題。

🔍 深度內容檢索：利用 Tavily API 針對特定議題進行網路搜尋，抓取多篇相關報導的完整內文，不只看標題。

🤖 AI 輿情分析：

綜合摘要：過濾雜訊，生成 150 字內的客觀懶人包。

核心衝突識別：AI 自動判斷該事件最大的爭議點或矛盾點。

多元觀點對照：自動歸納「支持方 vs 反對方」或「樂觀派 vs 悲觀派」的論述，並附上媒體來源。

🖥️ 互動式 Web UI：使用 Gradio 建置的簡潔介面，點擊左側議題即可即時生成右側報告。

🛡️ 穩定的輸出格式：採用 JSON Schema 強制 Gemini 輸出結構化資料，並包含自動修復機制，防止 AI 生成內容截斷。

🛠️ 技術架構
UI 介面: Gradio

LLM 模型: Google Gemini (gemini-2.5-flash 或 1.5-flash)

搜尋引擎: Tavily Search API (用於 RAG 檢索)

資料來源: Feedparser (RSS)

爬蟲輔助: BeautifulSoup4, Requests

🚀 快速開始

1. 前置需求

請確保你已安裝 Python 3.10 或以上版本，並且擁有以下 API Key：

Google AI Studio Key: 用於存取 Gemini 模型 (取得連結)

Tavily API Key: 用於搜尋新聞內文 (取得連結)

2. 安裝專案

# Clone 此專案
git clone https://github.com/your-username/ai-news-aggregator.git
cd ai-news-aggregator

# 建立虛擬環境 (建議)
python -m venv .venv
source .venv/bin/activate  # Mac/Linux
# .venv\Scripts\activate   # Windows

# 安裝依賴套件
pip install -r requirements.txt

3. 設定環境變數

在專案根目錄建立一個 .env 檔案，並填入你的 API Key：

# .env 檔案內容
GOOGLE_API_KEY=你的_Gemini_API_Key
TAVILY_API_KEY=你的_Tavily_API_Key

4. 啟動應用程式

python main.py

啟動後，終端機將會顯示一組 URL（通常是 (http://localhost:7860/)），在瀏覽器中開啟即可使用。

![image](https://github.com/user-attachments/assets/67c21c4c-dbc5-45c4-9525-c78ab517ddf0)

📝 授權 (License)

本專案採用 MIT License。
