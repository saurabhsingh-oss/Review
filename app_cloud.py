"""
app_cloud.py - CLOUD version. Review sentiment dashboard, NO browser.

This is the app you host on a permanent URL for your team. It does NOT scrape
Amazon (that must be done locally - see reviews.py). Instead, a user uploads
a reviews file produced locally and this app runs the sentiment + theme
analysis and lets them download the Excel report.

Accepted uploads:
  - the JSON file produced by the local tool  (rev_<ASIN>.json)
  - a CSV or Excel file that has at least a 'body' column

Run locally to test:  streamlit run app_cloud.py
Deploy: see DEPLOY.md (Streamlit Community Cloud, requirements_cloud.txt).
"""

import io
import json

import pandas as pd
import streamlit as st

from analyze import analyze_reviews, export_excel

st.set_page_config(page_title="TWT Review Sentiment", layout="centered")
st.title("Review Sentiment Dashboard")
st.caption("Prototype - The Whole Truth Foods. Upload reviews, get analysis.")

REQUIRED = ["asin", "rating", "title", "date", "verified", "body",
            "helpful", "review_id"]


def _normalize(records):
    """Ensure every record has the columns analyze_reviews expects."""
    df = pd.DataFrame(records)
    if "body" not in df.columns:
        # try common alternates
        for alt in ["review", "text", "Body", "review_body"]:
            if alt in df.columns:
                df = df.rename(columns={alt: "body"})
                break
    if "body" not in df.columns:
        raise ValueError("Uploaded file must have a 'body' column "
                         "(the review text).")
    for col in REQUIRED:
        if col not in df.columns:
            if col == "verified":
                df[col] = False
            elif col == "rating":
                df[col] = None
            else:
                df[col] = ""
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    df["verified"] = df["verified"].astype(bool)
    return df.to_dict("records")


def _load(upload):
    name = upload.name.lower()
    if name.endswith(".json"):
        return json.load(io.TextIOWrapper(upload, encoding="utf-8"))
    if name.endswith(".csv"):
        return pd.read_csv(upload).to_dict("records")
    if name.endswith((".xlsx", ".xls")):
        # if it's our own export, the reviews are on the 'Reviews' sheet
        xls = pd.ExcelFile(upload)
        sheet = "Reviews" if "Reviews" in xls.sheet_names else xls.sheet_names[0]
        return pd.read_excel(xls, sheet_name=sheet).to_dict("records")
    raise ValueError("Unsupported file type. Use .json, .csv, or .xlsx.")


with st.expander("How this works / how to get the reviews file", expanded=False):
    st.markdown(
        "1. On your own computer, run the local scraper (reviews.py) while "
        "signed into Amazon. It saves a reviews file.\n"
        "2. Upload that file here (JSON, CSV, or Excel with a 'body' column).\n"
        "3. This app runs sentiment + theme analysis - no browser needed, so "
        "it works on a hosted URL.\n\n"
        "Why the split? Scraping needs a real logged-in browser and your own "
        "IP; cloud servers get blocked by Amazon. Analysis has no such needs."
    )

upload = st.file_uploader("Upload a reviews file",
                          type=["json", "csv", "xlsx", "xls"])

if upload is not None:
    try:
        records = _normalize(_load(upload))
    except Exception as e:  # noqa: BLE001
        st.error(type(e).__name__ + ": " + str(e))
        st.stop()

    if not records:
        st.warning("The file has no rows.")
        st.stop()

    analyzed, summary, themes = analyze_reviews(records)
    st.success("Analysed " + str(len(analyzed)) + " reviews.")

    st.subheader("Summary")
    st.dataframe(summary, use_container_width=True, hide_index=True)
    st.bar_chart(analyzed["sentiment"].value_counts())

    st.subheader("Top themes")
    st.dataframe(themes, use_container_width=True, hide_index=True)

    st.subheader("Reviews")
    st.dataframe(analyzed, use_container_width=True, hide_index=True)

    buf = io.BytesIO()
    export_excel(analyzed, summary, themes, buf)
    st.download_button(
        "Download Excel (Summary + Themes + Reviews)",
        buf.getvalue(), file_name="review_analysis.xlsx",
        mime="application/vnd.openxmlformats-officedocument."
             "spreadsheetml.sheet")
else:
    st.info("Upload a reviews file to begin.")
