# **📰 自動新聞整合系統 (Automatic News Integration System)**

## **專案簡介**

本專案是一個基於 LLM 的自動化新聞報告生成系統。它旨在解決資訊爆炸時代中，使用者難以快速掌握每日新聞重點的問題。系統會從多個來源搜尋最新的台灣新聞，透過大型語言模型（LLM）提煉出核心事件，並綜合多方報導，生成一份客觀、有引用來源的綜合報告。

* **核心價值:** 大幅縮短新聞篩選與閱讀時間，提供多角度的事件全貌。  
* **目標受眾:** 內容編輯者、媒體分析師、或任何希望高效獲取台灣每日新聞摘要的一般使用者。

## **系統架構與技術棧**

| 流程階段 | 使用工具 | 核心功能 |
| :---- | :---- | :---- |
| **Phase 0 & 1 (標題與廣泛搜尋)** | Google Custom Search API / Tavily Search API | 獲取初始標題並進行初步內容探索。 |
| **Phase 2 & 3 (事件提取與摘要)** | **Google Gemini 2.5 Flash** | 提煉 3-5 個核心事件；綜合原始內容生成約 500 字的客觀摘要。 |
| **Phase 4 (輸出)** | Python datetime / I/O | 將最終報告格式化為 Markdown 檔案，並包含完整的來源連結。 |

## **快速入門 (Setup)**

### **1\. 安裝依賴套件**

請確保您的 Python 環境已安裝所有必要的函式庫：  
pip install python-dotenv tavily google-genai google-api-python-client

### **2\. 設定環境變數**

您需要從各個服務商獲取 API Keys，並在專案根目錄下創建一個名為 **.env** 的檔案，填入您的金鑰和 ID：  
TAVILY\_API\_KEY="您的 Tavily API Key"  
GOOGLE\_API\_KEY="您的 Google API Key (用於 Gemini 和 CSE)"  
GOOGLE\_CSE\_ID="您的 Google Custom Search Engine ID"


## **貢獻**

歡迎任何形式的貢獻！如果您對程式碼有任何建議或發現 Bug，請隨時提交 Pull Request 或開啟 Issue。
