from datetime import datetime, timedelta
import email.utils
import html
import os
import re
import smtplib
import time
import xml.etree.ElementTree as ET
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests

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

# 키워드 세트 (큰따옴표 포함 정확한 어구 검색)
KEYWORDS = ['"배터리 소재"', '"배터리 AI"', '"ESS 배터리"']


# ==========================================
# 2. 크롤링 및 필터링 도구 함수
# ==========================================
def clean_html(text):
    """HTML 태그 및 특수문자 제거 함수"""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return text.strip()


def is_within_last_24h(pub_date_str):
    """기사 작성일이 최근 24시간 이내인지 확인하는 함수"""
    try:
        pub_tuple = email.utils.parsedate_tz(pub_date_str)
        if pub_tuple:
            pub_timestamp = email.utils.mktime_tz(pub_tuple)
            pub_datetime = datetime.fromtimestamp(pub_timestamp)
            return datetime.now() - pub_datetime <= timedelta(hours=24)
    except Exception:
        pass
    return True


def get_naver_news(keyword, display=10):
    """네이버 뉴스 API - 관련도순(sim) 수집 및 최근 24시간 필터링"""
    url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display={display}&sort=sim"
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
                if is_within_last_24h(item.get("pubDate", "")):
                    news_list.append(
                        {
                            "source": "네이버 뉴스",
                            "title": clean_html(item.get("title", "")),
                            "link": item.get("originallink") or item.get("link", ""),
                            "description": clean_html(item.get("description", "")),
                        }
                    )
            return news_list[:3]
    except Exception as e:
        print(f"네이버 뉴스 수집 중 오류 발생: {e}")
    return []


def get_google_news(keyword, display=10):
    """구글 뉴스 RSS - 주요 뉴스 순 수집 및 최근 24시간 필터링"""
    url = f"https://news.google.com/rss/search?q={keyword}&hl=ko&gl=KR&ceid=KR:ko"

    try:
        res = requests.get(url)
        if res.status_code == 200:
            root = ET.fromstring(res.text)
            news_list = []
            for item in root.findall(".//item"):
                pub_date = (
                    item.find("pubDate").text
                    if item.find("pubDate") is not None
                    else ""
                )

                if is_within_last_24h(pub_date):
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
                if len(news_list) >= display:
                    break
            return news_list[:3]
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
        <p>안녕하세요. 설정하신 주요 키워드 관련 매일 아침 뉴스 브리핑입니다.</p>
        <hr style="border: 0; border-top: 1px solid #ccc;" />
    """

    for category, articles in news_data.items():
        clean_category = category.replace('"', '')
        html_content += f"<h3 style='color: #2b5797; margin-top: 20px;'>📌 {clean_category} 관련 뉴스</h3>"
        if not articles:
            html_content += "<p style='color: #777;'>최근 24시간 내 수집된 관련 뉴스가 없습니다.</p>"
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
        f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 뉴스 수집 및 이메일 전송 작업을 시작합니다..."
    )
    all_news = {}
    for kw in KEYWORDS:
        naver_res = get_naver_news(kw, display=10)
        google_res = get_google_news(kw, display=10)

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
# 4. 서버 자동 실행 시작점
# ==========================================
if __name__ == "__main__":
    job()
