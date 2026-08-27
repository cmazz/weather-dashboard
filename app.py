import sqlite3
from google import genai
import pandas as pd
import streamlit as st

# Read key securely from Streamlit Cloud Secrets
if "GEMINI_API_KEY" in st.secrets:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
else:
    st.error("GEMINI_API_KEY is missing from Streamlit Secrets.")
    st.stop()

st.set_page_config(page_title="Church Farm Weather", layout="wide")
st.title("Church Farm School Weather Dashboard")

# 1. Fetch saved records from SQLite
conn = sqlite3.connect("weather.db")
df = pd.read_sql_query("SELECT * FROM daily_weather", conn)
conn.close()

# --- DATA CLEANING & TYPE CONVERSION BLOCK ---
if not df.empty:
    # Safely convert date column to Datetime objects
    if "date" in df.columns:
        df["date_dt"] = pd.to_datetime(df["date"], errors="coerce")
    
    # Force weather metrics to numeric numbers (converts '---' or text to NaN)
    numeric_cols = ["temp_current", "humidity", "wind_speed", "bar_pressure", "rain_total"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            
    # Remove rows where dates could not be parsed
    df_clean = df.dropna(subset=["date_dt"]).sort_values("date_dt").copy()
else:
    df_clean = pd.DataFrame()
# ----------------------------------------------

# 2. Live KPI Summary Cards
if not df_clean.empty:
    latest = df_clean.iloc[-1]
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Temperature", f"{latest.get('temp_current', 0)} °F")
    col2.metric("Humidity", f"{latest.get('humidity', 0)} %")
    col3.metric("Wind Speed", f"{latest.get('wind_speed', 0)} mph")
    col4.metric("Barometer", f"{latest.get('bar_pressure', 0)} inHg")
    col5.metric("Rain Today", f"{latest.get('rain_total', 0)} in")

st.divider()

# 3. Station Data Trends
st.subheader("Station Data Log")
if not df_clean.empty:
    st.write("**Temperature, Humidity, & Wind Speed**")
    
    # Plot line chart safely with clean numeric columns
    chart_cols = [c for c in ["temp_current", "humidity", "wind_speed"] if c in df_clean.columns]
    if chart_cols:
        st.line_chart(df_clean.set_index("date_dt")[chart_cols])

    st.write("**Daily Precipitation (Inches)**")
    if "rain_total" in df_clean.columns:
        st.bar_chart(df_clean.set_index("date_dt")["rain_total"])

    st.dataframe(
        df_clean.sort_values(by="date_dt", ascending=False), width="stretch"
    )
else:
    st.info("No records logged yet. Run database.py or import_csvs.py first.")

st.divider()

# 4. Interactive Q&A Assistant
st.subheader("Ask Questions About Station History")
user_question = st.text_input(
    "Ask a question about your weather history:",
    placeholder="e.g., What was the average temperature in January 2025?",
)

if st.button("Ask Assistant") and user_question:
    if df_clean.empty:
        st.warning("No historical data available to query.")
    else:
        with st.spinner("Analyzing weather database..."):
            try:
                df_clean["month"] = df_clean["date_dt"].dt.strftime("%B %Y")

                monthly_summary = df_clean.groupby("month").agg(
                    avg_temp=("temp_current", "mean"),
                    max_temp=("temp_current", "max"),
                    min_temp=("temp_current", "min"),
                    total_rain=("rain_total", "sum"),
                    avg_humidity=("humidity", "mean"),
                    day_count=("temp_current", "count"),
                ).round(2).to_string()

                recent_records = df_clean.sort_values(by="date_dt", ascending=False).head(60).to_string(index=False)

                client = genai.Client(api_key=GEMINI_API_KEY)
                prompt = (
                    "You are an expert meteorological data analyst for Church Farm School.\n"
                    "Use the PRE-CALCULATED MONTHLY SUMMARY table below for all overall averages, totals, and monthly stats.\n"
                    "Do NOT attempt to re-sum raw rows manually.\n\n"
                    f"PRE-CALCULATED MONTHLY STATS:\n{monthly_summary}\n\n"
                    f"RECENT DAILY RECORDS (LAST 60 DAYS):\n{recent_records}\n\n"
                    f"User Question: {user_question}"
                )

                response = client.models.generate_content(
                    model="gemini-3.6-flash", contents=prompt
                )

                st.markdown("**Answer:**")
                st.write(response.text)
            except Exception as e:
                st.error(f"Error answering question: {e}")

# 5. AI Forecast Analysis
st.subheader("AI Microclimate Predictions")
if st.button("Generate Weather Predictions"):
    if df_clean.empty:
        st.warning("No historical data available to predict.")
    else:
        with st.spinner("Analyzing weather patterns with Gemini..."):
            try:
                client = genai.Client(api_key=GEMINI_API_KEY)
                recent_data = df_clean.tail(30).to_string()

                prompt = (
                    "You are an expert meteorologist analyzing station observations for Church Farm School. "
                    "Analyze these weather observations (including temperature, humidity, wind, barometric pressure, dew point, and rainfall) "
                    "and provide:\n"
                    "1. Summary of recent local weather conditions.\n"
                    "2. Detailed forecast for tomorrow.\n"
                    "3. Extended weekly outlook for the campus.\n\n"
                    f"Data:\n{recent_data}"
                )

                response = client.models.generate_content(
                    model="gemini-3.6-flash", contents=prompt
                )

                st.markdown(response.text)
            except Exception as e:
                st.error(f"Error generating prediction: {e}")
