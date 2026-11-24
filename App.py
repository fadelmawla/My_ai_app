import os
import requests
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

OPENROUTER_API_KEY = os.environ.get(
    "OPENROUTER_API_KEY",
    "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"
).strip()

MODEL_NAME = os.environ.get("MODEL_NAME", "qwen/qwen-2.5-7b-instruct:free")
SYSTEM_PROMPT = os.environ.get(
    "SYSTEM_PROMPT",
    "أنت مساعد ذكي ومباشر وواضح. أجب بدقة وبدون تعقيد."
)

def web_search(query):
    try:
        url = "https://api.duckduckgo.com/"
        params = {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1}
        res = requests.get(url, params=params, timeout=8).json()
        snippets = []
        if res.get("AbstractText"):
            snippets.append(res["AbstractText"])
        for item in res.get("RelatedTopics", [])[:4]:
            if isinstance(item, dict) and item.get("Text"):
                snippets.append(item["Text"])
        return "\n".join(snippets) if snippets else ""
    except Exception:
        return ""

HTML_PAGE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>تطبيقي الذكي</title>
<style>
  body { font-family: Tahoma, Arial, sans-serif; background: #111; color: #eee; margin: 0; padding: 16px; }
  .box { max-width: 600px; margin: auto; background: #1c1c1c; padding: 16px; border-radius: 12px; }
  #chat { height: 62vh; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; margin-bottom: 12px; }
  .msg { padding: 10px 14px; border-radius: 10px; line-height: 1.5; white-space: pre-wrap; }
  .user { background: #2b5278; align-self: flex-start; }
  .bot { background: #2a2a2a; align-self: flex-end; }
  .row { display: flex; gap: 8px; }
  input { flex: 1; padding: 12px; border-radius: 8px; border: none; background: #2e2e2e; color: #fff; font-size: 15px; }
  button { padding: 12px 18px; border-radius: 8px; border: none; background: #5b4ce2; color: #fff; font-weight: bold; cursor: pointer; }
</style>
</head>
<body>
<div class="box">
  <h3 style="margin-top:0;">تطبيقي الذكي</h3>
  <div id="chat"></div>
  <div class="row">
    <input id="inp" type="text" placeholder="اكتب سؤالك هنا..." />
    <button onclick="sendMsg()">إرسال</button>
  </div>
</div>
<script>
async function sendMsg() {
  const inp = document.getElementById("inp");
  const chat = document.getElementById("chat");
  const text = inp.value.trim();
  if (!text) return;
  chat.innerHTML += `<div class="msg user">${text}</div>`;
  inp.value = "";
  chat.scrollTop = chat.scrollHeight;

  const loading = document.createElement("div");
  loading.className = "msg bot";
  loading.innerText = "جاري التفكير والبحث...";
  chat.appendChild(loading);
  chat.scrollTop = chat.scrollHeight;

  try {
    const r = await fetch("/ask", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({message: text})
    });
    const data = await r.json();
    loading.innerText = data.reply || data.error || "لم يصدر رد";
  } catch (e) {
    loading.innerText = "حصل خطأ بالاتصال بالسيرفر";
  }
  chat.scrollTop = chat.scrollHeight;
}
</script>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML_PAGE)

@app.route("/ask", methods=["POST"])
def ask():
    if not OPENROUTER_API_KEY:
        return jsonify({"error": "مفتاح OPENROUTER_API_KEY غير مضبوط"}), 400

    data = request.get_json(force=True)
    user_msg = (data.get("message") or "").strip()
    if not user_msg:
        return jsonify({"error": "الرسالة فارغة"}), 400

    search_info = web_search(user_msg)
    prompt_content = user_msg
    if search_info:
        prompt_content = f"معلومات من البحث بالإنترنت:\n{search_info}\n\nسؤال المستخدم:\n{user_msg}"

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL_NAME,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt_content},
                ],
            },
            timeout=45,
        )
        result = resp.json()
        if "choices" in result:
            reply = result["choices"][0]["message"]["content"]
            return jsonify({"reply": reply})
        return jsonify({"error": str(result)}), 400
    except Exception as e:
        return jsonify({"error": f"خطأ أثناء التواصل مع النموذج: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
