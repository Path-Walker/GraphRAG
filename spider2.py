from selenium import webdriver
from selenium.webdriver.common.by import By
import time

# =========================
# 参数
# =========================
KEYWORD = "openclaw龙虾"
BASE_URL = "https://s.weibo.com/weibo"

options = webdriver.EdgeOptions()
options.add_argument("--start-maximized")

driver = webdriver.Edge(options=options)

# =========================
# 登录
# =========================
driver.get("https://weibo.com")
print("请在30秒内登录...")
time.sleep(30)

results = []

# =========================
# 爬前5页
# =========================
for page in range(1, 6):
    print(f"\n正在爬第 {page} 页...")

    url = f"{BASE_URL}?q={KEYWORD}&page={page}&xsort=hot&suball=1"
    driver.get(url)

    posts = driver.find_elements(By.CSS_SELECTOR, "div.card-wrap")

    for p in posts:
        text = p.text.strip()

        # ⭐ 防止第一页空卡
        if len(text) < 20:
            continue

        lines = text.split("\n")

        user = lines[0] if lines else "未知"
        content = max(lines, key=len)

        results.append({
            "page": page,
            "user": user,
            "content": content
        })

# =========================
# 输出结果
# =========================
print("\n========== 爬取结果 ==========\n")

for r in results:
    print(f"[第{r['page']}页]")
    print("用户：", r["user"])
    print("内容：", r["content"])
    print("-" * 50)

driver.quit()