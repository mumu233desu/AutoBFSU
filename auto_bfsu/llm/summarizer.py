import json
import requests
from ..config import Config

class BaseSummarizer:
    def summarize(self, title: str, content: str) -> dict:
        """
        Summarize a notification and calculate its relevance score.
        Returns: {
            'summary': str,
            'category': str,
            'relevance_score': int (0-100),
            'reason': str
        }
        """
        raise NotImplementedError

class LLMSummarizer(BaseSummarizer):
    def __init__(self):
        self.api_key = Config.LLM_API_KEY
        self.base_url = Config.LLM_BASE_URL
        self.model = Config.LLM_MODEL
        self.keywords = Config.KEYWORDS

    def summarize(self, title: str, content: str) -> dict:
        """
        Summarize the notification. Attempts to use LLM. 
        If LLM is unconfigured or fails, falls back to HeuristicSummarizer.
        """
        if not self.api_key or self.api_key.upper() in ["YOUR_LLM_API_KEY_HERE", "YOUR_API_KEY_HERE", "YOUR_LLM_API_KEY"] or "your_llm_api_key_here" in self.api_key.lower():
            print("[LLMSummarizer] API Key not set or using placeholder. Using local heuristic summarizer.")
            return HeuristicSummarizer().summarize(title, content)

        # Standard Prompt
        prompt = f"""你是一个智能北外助手。请对以下学校通知进行摘要，并智能评估该通知与学生的实际相关度（关注方向：{", ".join(self.keywords)}）。

【关键评估要求 - 语义分析而非生硬词语匹配】：
1. 提供的关注方向仅为线索，严禁只因为通知文本中含有某一个字词而给出高分！
2. 请进行【深度语义分析】：判断该通知是否需要该学生“采取行动”或“高度关注”。
3. 任何【过去事件总结报告】（如：某研讨会圆满结束、外宾来访、某院系开展了某学习活动等新闻性通知），由于学生无需采取任何行动，请一律评定为“低相关度”（相关度分数 0-30）。
4. 任何【面向特定极少数或非学生群体】的通知（如：面向外籍学生的汉语桥夏令营、教职工体检等），对普通本科生而言，也请一律评定为“低相关度”（相关度分数 0-30）。
5. 只有真正关乎“选课安排、必修/选修学分、课程签到、全校考试、重大放假安排、学分冲抵、专业核心讲座”等对学生日常学习/生活有直接影响的通知，才可以评为“中”（40-79）或“高”（80-100）相关度。

通知标题: {title}
通知全文:
{content[:1000]} # Limit to 1000 chars to save tokens

请以 JSON 格式输出，不要包含 Markdown 格式标记（如 ```json 等），严格包含以下字段：
{{
  "summary": "一句精炼的摘要，不超过30字",
  "category": "教学/行政/学生活动/讲座/生活服务/其他",
  "relevance_score": 0到100的整数分值,
  "relevance_summary": "一句话精炼评估该通知对学生是否有实际价值或需采取何种行动（不超过30字）"
}}"""

        try:
            # Let's use a standard requests call to the OpenAI compatible endpoint.
            # This is extremely robust and avoids any version incompatibilities of the openai package.
            url = f"{self.base_url.rstrip('/')}/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant that strictly outputs JSON."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "response_format": {"type": "json_object"}
            }

            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            if resp.status_code == 200:
                result = resp.json()
                content_text = result["choices"][0]["message"]["content"].strip()
                # Clean up any potential markdown wraps
                content_text = re_clean_json(content_text)
                parsed = json.loads(content_text)
                
                # Validate output structure
                relevance_summary = parsed.get('relevance_summary', parsed.get('reason', 'AI 自动分析'))
                return {
                    'summary': parsed.get('summary', title[:30]),
                    'category': parsed.get('category', '其他'),
                    'relevance_score': int(parsed.get('relevance_score', 0)),
                    'relevance_summary': relevance_summary,
                    'reason': relevance_summary  # Keep reason for backward compatibility
                }
            else:
                print(f"[LLMSummarizer] API error (status {resp.status_code}): {resp.text}. Falling back to Heuristic.")
                return HeuristicSummarizer().summarize(title, content)

        except Exception as e:
            print(f"[LLMSummarizer] Exception during LLM query: {e}. Falling back to Heuristic.")
            return HeuristicSummarizer().summarize(title, content)


class HeuristicSummarizer(BaseSummarizer):
    def __init__(self):
        self.keywords = Config.KEYWORDS

    def summarize(self, title: str, content: str) -> dict:
        """
        Fallback heuristic summarizer based on keyword matching.
        """
        # Calculate a basic relevance score
        matched_keywords = []
        score = 0
        
        full_text = (title + "\n" + content).lower()
        for kw in self.keywords:
            if kw.lower() in full_text:
                matched_keywords.append(kw)
                score += 25
        
        score = min(score, 100)  # Max out at 100
        
        # Categorization heuristics
        category = "其他"
        if any(x in title for x in ["课", "教学", "选修", "学分", "考试", "补考", "成绩"]):
            category = "教学服务"
        elif any(x in title for x in ["奖学金", "资助", "违纪", "宿舍", "学生活动", "团"]):
            category = "学生活动"
        elif any(x in title for x in ["讲座", "报告", "学术", "沙龙"]):
            category = "讲座学术"
        elif any(x in title for x in ["停电", "停水", "维修", "校医院", "缴费", "一卡通"]):
            category = "生活服务"
        elif any(x in title for x in ["放假", "值班", "关于", "通知"]):
            category = "行政通知"

        # Formulate a basic summary
        summary = title
        if len(summary) > 30:
            summary = summary[:27] + "..."

        if matched_keywords:
            relevance_summary = f"命中您的关注关键词 {', '.join(matched_keywords[:3])}，相关度较高。"
        else:
            relevance_summary = f"未命中您的关注关键词（{', '.join(self.keywords[:3])}...），相关度较低。"

        return {
            'summary': summary,
            'category': category,
            'relevance_score': score,
            'relevance_summary': relevance_summary,
            'reason': relevance_summary  # Keep reason for backward compatibility
        }

def re_clean_json(text: str) -> str:
    """Helper to strip markdown block fences if returned by LLM."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()
