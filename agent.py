import html
import os  # ★ 맨 위에 os 모듈 추가
import re
import smtplib
import time
import xml.etree.ElementTree as ET
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
import schedule

# ==========================================
# 1. 설정 정보 (GitHub Secrets에서 가져오기)
# ==========================================
NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET")

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "hyeodongjang@gmail.com"
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")
RECEIVER_EMAIL = "hyeodongjang@gmail.com"

KEYWORDS = ["배터리", "이차전지", "K-배터리"]

# ==========================================
# 2. 크롤링 및 변환 도구 함수
# ==========================================
def clean_html(text):
    """HTML 태그 및 특수문자 제거 함수"""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return text.strip()


def get_naver_news(keyword, display=5):
    """네이버 뉴스 API로 최신 뉴스 수집"""
    url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display={display}&sort=date"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }

    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            items = res.json().get("items", [])
            news_list = []
            for item in items:
                news_list.append(
                    {
                        "source": "네이버 뉴스",
                        "title": clean_html(item.get("title", "")),
                        "link": item.get("originallink") or item.get("link", ""),
                        "description": clean_html(item.get("description", "")),
                    }
                )
            return news_list
    except Exception as e:
        print(f"네이버 뉴스 수집 중 오류 발생: {e}")
    return []


def get_google_news(keyword, display=5):
    """구글 뉴스 RSS로 최신 뉴스 수집"""
    url = f"https://news.google.com/rss/search?q={keyword}&hl=ko&gl=KR&ceid=KR:ko"

    try:
        res = requests.get(url)
        if res.status_code == 200:
            root = ET.fromstring(res.text)
            news_list = []
            for item in root.findall(".//item")[:display]:
                title = (
                    item.find("title").text
                    if item.find("title") is not None
                    else ""
                )
                link = (
                    item.find("link").text
                    if item.find("link") is not None
                    else ""
                )
                news_list.append(
                    {
                        "source": "구글 뉴스",
                        "title": clean_html(title),
                        "link": link,
                        "description": "구글 뉴스 원문 참고",
                    }
                )
            return news_list
    except Exception as e:
        print(f"구글 뉴스 수집 중 오류 발생: {e}")
    return []


def send_email(news_data):
    """수집된 뉴스를 HTML 이메일로 전송"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = (
        f"⚡ [데일리 리포트] 배터리 산업 핵심 뉴스 브리핑 ({time.strftime('%Y-%m-%d')})"
    )
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #1a73e8;">⚡ 오늘의 배터리 산업 핵심 뉴스</h2>
        <p>안녕하세요. 설정하신 배터리/이차전지 관련 매일 아침 브리핑입니다.</p>
        <hr style="border: 0; border-top: 1px solid #ccc;" />
    """

    for category, articles in news_data.items():
        html_content += f"<h3 style='color: #2b5797; margin-top: 20px;'>📌 {category} 관련 뉴스</h3>"
        if not articles:
            html_content += "<p style='color: #777;'>관련 뉴스가 없습니다.</p>"
            continue

        html_content += "<ul style='padding-left: 20px;'>"
        for article in articles:
            html_content += f"""
            <li style="margin-bottom: 12px;">
                <strong style="font-size: 14px;">[{article['source']}] <a href="{article['link']}" target="_blank" style="color: #1a73e8; text-decoration: none;">{article['title']}</a></strong><br>
                <span style="font-size: 12px; color: #555;">{article['description']}</span>
            </li>
            """
        html_content += "</ul>"

    html_content += """
        <hr style="border: 0; border-top: 1px solid #ccc;" />
        <p style="font-size: 11px; color: #888;">본 메일은 자동화된 뉴스 브리핑 에이전트에 의해 발송되었습니다.</p>
    </body>
    </html>
    """

    msg.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        print("✅ 이메일 전송이 성공적으로 완료되었습니다!")
    except Exception as e:
        print(f"❌ 이메일 전송 실패: {e}")


# ==========================================
# 3. 종합 실행 함수 (job)
# ==========================================
def job():
    print(
        f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 뉴스 수집 및 이메일 전송 작업을"
        " 시작합니다..."
    )
    all_news = {}
    for kw in KEYWORDS:
        naver_res = get_naver_news(kw, display=3)
        google_res = get_google_news(kw, display=3)

        combined = naver_res + google_res
        seen_links = set()
        unique_news = []
        for news in combined:
            if news["link"] not in seen_links:
                seen_links.add(news["link"])
                unique_news.append(news)

        all_news[kw] = unique_news

    send_email(all_news)


# ==========================================
# 4. 실행 및 스케줄러 설정
# ==========================================
# 서버가 코드를 불러오면 뉴스를 수집해 이메일을 1회 전송하고 끝납니다.
job()