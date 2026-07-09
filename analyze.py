"""
analyze.py - Sentiment analysis + theme extraction + Excel export for reviews.

Sentiment uses VADER (lexicon-based, lightweight, no model download).
No Playwright here, so this runs safely inside Streamlit's thread.
"""

import re
from collections import Counter
from typing import Optional

import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_ANALYZER = SentimentIntensityAnalyzer()

_STOP = set("""
a an the and or but if then else for to of in on at by with from as is are was
were be been being this that these those it its i me my we our you your they
them their he she his her not no so very just too also more most much many any
all some such can could would should will shall may might do does did done have
has had having get got than into out up down off over under again once here there
when where why how what which who whom about product amazon item order buy bought
use used using one two really thing things good bad ok okay im ive dont didnt
""".split())

_WORD = re.compile(r"[a-zA-Z][a-zA-Z'-]+")


def _clean_tokens(text):
    toks = [t.lower() for t in _WORD.findall(text or "")]
    return [t for t in toks if t not in _STOP and len(t) > 2]


def _label_from_score(score):
    if score >= 0.05:
        return "Positive"
    if score <= -0.05:
        return "Negative"
    return "Neutral"


def _label_from_star(star: Optional[float]):
    if star is None:
        return "Unknown"
    if star >= 4:
        return "Positive"
    if star <= 2:
        return "Negative"
    return "Neutral"


def analyze_reviews(reviews):
    """Return (analyzed_df, summary_df, themes_df)."""
    df = pd.DataFrame(reviews)
    if df.empty:
        return df, pd.DataFrame(), pd.DataFrame()

    scores, sent, star_sent = [], [], []
    for _, row in df.iterrows():
        text = str(row.get("title") or "") + ". " + str(row.get("body") or "")
        s = _ANALYZER.polarity_scores(text)["compound"]
        scores.append(round(s, 4))
        sent.append(_label_from_score(s))
        star_sent.append(_label_from_star(row.get("rating")))

    df["sentiment_score"] = scores
    df["sentiment"] = sent
    df["star_sentiment"] = star_sent

    n = len(df)
    avg_star = (round(df["rating"].dropna().mean(), 2)
                if df["rating"].notna().any() else None)
    summary_rows = [
        ("Total reviews collected", n),
        ("Average star rating", avg_star),
        ("Verified purchase %", round(100 * df["verified"].mean(), 1)),
        ("", ""),
        ("Sentiment (text) - Positive", int((df["sentiment"] == "Positive").sum())),
        ("Sentiment (text) - Neutral", int((df["sentiment"] == "Neutral").sum())),
        ("Sentiment (text) - Negative", int((df["sentiment"] == "Negative").sum())),
        ("", ""),
    ]
    for star in [5, 4, 3, 2, 1]:
        summary_rows.append((str(star) + "-star reviews",
                             int((df["rating"] == star).sum())))
    summary_df = pd.DataFrame(summary_rows, columns=["Metric", "Value"])

    def _top_terms(subset, k=20):
        uni, bi = Counter(), Counter()
        for _, row in subset.iterrows():
            toks = _clean_tokens(str(row.get("title") or "") + " "
                                 + str(row.get("body") or ""))
            uni.update(toks)
            bi.update(a + " " + b for a, b in zip(toks, toks[1:]))
        return (uni + bi).most_common(k)

    pos = _top_terms(df[df["sentiment"] == "Positive"])
    neg = _top_terms(df[df["sentiment"] == "Negative"])
    themes_df = pd.DataFrame({
        "Positive theme": [t for t, _ in pos] + [""] * (20 - len(pos)),
        "Pos count": [c for _, c in pos] + [""] * (20 - len(pos)),
        "Negative theme": [t for t, _ in neg] + [""] * (20 - len(neg)),
        "Neg count": [c for _, c in neg] + [""] * (20 - len(neg)),
    })

    cols = ["rating", "star_sentiment", "sentiment", "sentiment_score",
            "title", "body", "date", "verified", "helpful", "review_id", "asin"]
    df = df[[c for c in cols if c in df.columns]]
    return df, summary_df, themes_df


def export_excel(analyzed_df, summary_df, themes_df, path):
    with pd.ExcelWriter(path, engine="openpyxl") as xl:
        summary_df.to_excel(xl, sheet_name="Summary", index=False)
        themes_df.to_excel(xl, sheet_name="Themes", index=False)
        analyzed_df.to_excel(xl, sheet_name="Reviews", index=False)
    return path
