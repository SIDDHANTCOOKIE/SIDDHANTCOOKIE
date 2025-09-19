#!/usr/bin/env python3
"""
update_stats.py
Fetch GitHub stats and fill stats_template.svg -> writes stats.svg

Usage: set environment variables:
  GITHUB_USERNAME (or pass as first arg)
  GITHUB_TOKEN (recommended) OR PAT in env (script will auto-detect)
  BIRTHDATE (YYYY-MM-DD) if you want uptime/age from birthday (optional)
  EMAIL, LINKEDIN, DISCORD, DISPLAY_NAME, OS_TEXT, IDE_TEXT, PROGRAMMING_LANGUAGES, SPOKEN_LANGUAGES, HOBBIES_SOFTWARE, HOBBIES_HARDWARE, HOST, KERNEL

The workflow included in repo sets these by passing inputs or reading from the file.
"""

import os
import sys
import requests
import math
from datetime import datetime, date
from time import sleep

# Configurable / pulled from env or hardcoded here
GITHUB_USERNAME = os.environ.get("GITHUB_USERNAME") or (sys.argv[1] if len(sys.argv) > 1 else "SIDDHANTCOOKIE")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("PAT") or os.environ.get("INPUT_TOKEN")
TEMPLATE_PATH = "stats_template.svg"
OUT_PATH = "stats.svg"

# Personal details (defaults come from your provided JSON)
DISPLAY_NAME = os.environ.get("DISPLAY_NAME", "Siddhant Kaushik")
EMAIL = os.environ.get("EMAIL", "siddhantkk27@gmail.com.com")
GITHUB_HANDLE = os.environ.get("GITHUB_HANDLE", GITHUB_USERNAME)
LINKEDIN = os.environ.get("LINKEDIN", "siddhant-kaushik-srm")
DISCORD = os.environ.get("DISCORD", "SIDDHANTCOOKIE")
BIRTHDATE = os.environ.get("BIRTHDATE", "2005-06-27")  # YYYY-MM-DD
OS_TEXT = os.environ.get("OS_TEXT", "Windows 11, Linux (WSL)")
IDE_TEXT = os.environ.get("IDE_TEXT", "VSCode, PyCharm")
PROGRAMMING_LANGUAGES = os.environ.get("PROGRAMMING_LANGUAGES", "Python, C, JavaScript, C++, JAVA")
SPOKEN_LANGUAGES = os.environ.get("SPOKEN_LANGUAGES", "English, Hindi, Japanese")
HOBBIES_SOFTWARE = os.environ.get("HOBBIES_SOFTWARE", "Hackathons, Building Apps, Exploring AI/Blockchain")
HOBBIES_HARDWARE = os.environ.get("HOBBIES_HARDWARE", "Exploring AI/Blockchain")
HOST = os.environ.get("HOST", "SRM University, KTR")
KERNEL = os.environ.get("KERNEL", "B.Tech CSE Freshman")

HEADERS = {"Accept": "application/vnd.github.v3+json"}
if TOKEN:
    HEADERS["Authorization"] = f"token {TOKEN}"

API = "https://api.github.com"

def iso_now():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def age_from_birthdate(birthdate_str):
    try:
        b = datetime.strptime(birthdate_str, "%Y-%m-%d").date()
        today = date.today()
        years = today.year - b.year - ((today.month, today.day) < (b.month, b.day))
        # derive months/days approx for style
        months = (today.month - b.month - (today.day < b.day)) % 12
        days = (today - date(today.year, today.month, b.day if today.day>=b.day else b.day)).days
        return f"{years} years, {months} months"
    except Exception:
        return "N/A"

def request_json(url, params=None):
    resp = requests.get(url, headers=HEADERS, params=params)
    if resp.status_code == 202:
        # GitHub sometimes returns 202 while generating statistics; wait a bit
        sleep(1)
        resp = requests.get(url, headers=HEADERS, params=params)
    resp.raise_for_status()
    return resp.json()

def fetch_user(username):
    return request_json(f"{API}/users/{username}")

def fetch_repos(username):
    repos = []
    page = 1
    while True:
        r = request_json(f"{API}/users/{username}/repos", params={"per_page": 100, "page": page, "type": "owner", "sort": "pushed"})
        if not r:
            break
        repos.extend(r)
        if len(r) < 100:
            break
        page += 1
    return repos

def fetch_repo_contribs(owner, repo):
    # contributors endpoint lists {login, contributions} - we'll try to find username
    try:
        return request_json(f"{API}/repos/{owner}/{repo}/contributors", params={"per_page": 100})
    except requests.HTTPError:
        return []

def fetch_repo_languages(owner, repo):
    try:
        return request_json(f"{API}/repos/{owner}/{repo}/languages")
    except requests.HTTPError:
        return {}

def safe_int(x):
    try:
        return int(x)
    except Exception:
        return 0

def estimate_loc_from_language_bytes(lang_bytes_sum):
    # heuristic: assume ~50 bytes per LOC (very rough). You can change this if you want.
    bytes_per_loc = 50
    loc = int(lang_bytes_sum / bytes_per_loc)
    return loc

def main():
    print(f"[+] Fetching GitHub data for: {GITHUB_USERNAME}")
    user = fetch_user(GITHUB_USERNAME)
    repos = fetch_repos(GITHUB_USERNAME)
    repo_count = len(repos)
    star_count = sum(r.get("stargazers_count", 0) for r in repos)
    follower_count = user.get("followers", 0)

    contrib_count = 0
    commit_count = 0
    total_lang_bytes = 0
    # iterate repos and fetch languages & contributors for commit counts
    for r in repos:
        name = r["name"]
        owner = r["owner"]["login"]
        # languages -> bytes
        langs = fetch_repo_languages(owner, name)
        total_lang_bytes += sum(langs.values()) if isinstance(langs, dict) else 0
        # contributors -> find matching username contributions
        contribs = fetch_repo_contribs(owner, name)
        for c in contribs:
            if c.get("login", "").lower() == GITHUB_USERNAME.lower():
                contrib_count += 1  # count repo contributed to
                commit_count += c.get("contributions", 0)
                break
        # small sleep to be polite
        sleep(0.1)

    loc_est = estimate_loc_from_language_bytes(total_lang_bytes)
    # Simple heuristic for "additions/deletions" placeholders:
    loc_add = int(loc_est * 0.85)
    loc_del = loc_est - loc_add

    # Age from birthdate
    age_text = age_from_birthdate(BIRTHDATE)

    updated_at = iso_now()

    # read template
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        svg = f.read()

    # replacements
    replacements = {
        "__DISPLAY_NAME__": DISPLAY_NAME,
        "__OS_TEXT__": OS_TEXT,
        "__AGE__": age_text,
        "__HOST__": HOST,
        "__KERNEL__": KERNEL,
        "__IDE__": IDE_TEXT,
        "__PROGRAMMING_LANGUAGES__": PROGRAMMING_LANGUAGES,
        "__SPOKEN_LANGUAGES__": SPOKEN_LANGUAGES,
        "__HOBBIES_SOFTWARE__": HOBBIES_SOFTWARE,
        "__HOBBIES_HARDWARE__": HOBBIES_HARDWARE,
        "__EMAIL__": EMAIL,
        "__GITHUB__": GITHUB_HANDLE,
        "__LINKEDIN__": LINKEDIN,
        "__DISCORD__": DISCORD,
        "__REPO_COUNT__": str(repo_count),
        "__CONTRIB_COUNT__": str(contrib_count),
        "__STAR_COUNT__": str(star_count),
        "__COMMIT_COUNT__": str(commit_count),
        "__FOLLOWER_COUNT__": str(follower_count),
        "__LOC_EST__": f"{loc_est:,}",
        "__LOC_ADD__": f"{loc_add:,}",
        "__LOC_DEL__": f"{loc_del:,}",
        "__UPDATED_AT__": updated_at,
    }

    for k, v in replacements.items():
        svg = svg.replace(k, v)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg)

    print(f"[+] Wrote {OUT_PATH} (repos={repo_count}, stars={star_count}, commits={commit_count}, followers={follower_count}, loc_est={loc_est})")

if __name__ == "__main__":
    main()
