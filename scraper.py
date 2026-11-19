import sqlite3
import time
import re
import requests
from bs4 import BeautifulSoup

# 1. SQLiteデータベースとテーブルの作成
DB_NAME = "google_repos.db"
conn = sqlite3.connect(DB_NAME)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS repositories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    language TEXT,
    stars INTEGER
)
""")
cur.execute("DELETE FROM repositories")
conn.commit()

# 2. スクレイピング処理
base_url = "https://github.com/orgs/google/repositories"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8"
}

page = 1
total_count = 0

print("スクレイピングを開始します...")

while True:
    url = f"{base_url}?page={page}"
    print(f"Page {page} を取得中...")

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"アクセス終了 (Status: {response.status_code})")
        break

    soup = BeautifulSoup(response.text, "html.parser")

    # hrefが "/google/リポジトリ名" の形になっているリンクをすべて探す
    repo_links = soup.find_all("a", href=re.compile(r"^/google/[^/]+$"))

    # 重複を除外してリポジトリの行（親のliやdiv）を特定する
    seen_names = set()
    page_items = []

    for link in repo_links:
        repo_name = link.get_text(strip=True)
        # メニュー等の不要なリンクを除外
        if not repo_name or repo_name in seen_names or repo_name in ["Repositories", "People", "Projects", "Packages"]:
            continue

        # リンクを囲っている一番近いリスト要素 (li または div) を親として取得
        container = link.find_parent("li") or link.find_parent("div", class_=re.compile(r"Box-row|listItem|ListItem", re.I))
        if container:
            seen_names.add(repo_name)
            page_items.append((repo_name, container))

    if not page_items:
        print("これ以上リポジトリが見つからないため終了します。")
        break

    for repo_name, container in page_items:
        # --- 主要な言語の取得 ---
        lang_tag = container.select_one("span[itemprop='programmingLanguage']")
        if not lang_tag:
            # 言語名の隣にある色丸アイコンの直後のテキスト等を探すフォールバック
            lang_span = container.find("span", class_=re.compile(r"repo-language-color"))
            if lang_span and lang_span.find_next_sibling("span"):
                lang_tag = lang_span.find_next_sibling("span")
        language = lang_tag.get_text(strip=True) if lang_tag else "None"

        # --- スター数の取得 ---
        star_tag = container.select_one(f"a[href='/google/{repo_name}/stargazers']")
        if star_tag:
            star_text = star_tag.get_text(strip=True).replace(",", "")
            if "k" in star_text.lower():
                stars = int(float(star_text.lower().replace("k", "")) * 1000)
            else:
                stars = int(star_text) if star_text.isdigit() else 0
        else:
            stars = 0

        cur.execute(
            "INSERT INTO repositories (name, language, stars) VALUES (?, ?, ?)",
            (repo_name, language, stars)
        )
        total_count += 1

    conn.commit()
    print(f"  -> {len(page_items)} 件取得（累計: {total_count} 件）")
    page += 1
    time.sleep(1)

print(f"\n完了！合計 {total_count} 件のリポジトリを保存しました。\n")

# 3. 保存したデータをSELECT文で表示する
cur.execute("SELECT id, name, language, stars FROM repositories LIMIT 20")
for row in cur.fetchall():
    print(f"ID: {row[0]} | リポジトリ名: {row[1]} | 言語: {row[2]} | スター数: {row[3]}")

conn.close()