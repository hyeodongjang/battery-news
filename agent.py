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
        # RFC 2822 형식 날짜 파싱 (예: Tue, 13 Oct 2026 08:00:00 +0900)
        pub_tuple = email.utils.parsedate_tz(pub_date_str)
        if pub_tuple:
            pub_timestamp = email.utils.mktime_tz(pub_tuple)
            pub_datetime = datetime.fromtimestamp(pub_timestamp)
            # 최근 24시간 이내 기사만 True
            return datetime.now() - pub_datetime <= timedelta(hours=24)
    except Exception:
        pass
    return True  # 파싱 실패 시 기본 포함


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
                # 24시간 이내 기사만 추려내기
                if is_within_last_24h(item.get("pubDate", "")):
                    news_list.append(
                        {
                            "source": "네이버 뉴스",
                            "title": clean_html(item.get("title", "")),
                            "link": item.get("originallink") or item.get("link", ""),
                            "description": clean_html(item.get("description", "")),
                        }
                    )
            return news_list[:3]  # 상위 3개 반환
    except Exception as e:
        print(f"네이버 뉴스 수집 중 오류 발생: {e}")
    return []


def get_google_news(keyword, display=10):
    """구글 뉴스 RSS - 주요 뉴스 순 수집 및 최근 24시간 필터링"""
    url = f"https://news.google.com/rss/search?q={keyword}&hl=ko&gl=KR&ceid=KR:ko"

    try:
        res = requests
