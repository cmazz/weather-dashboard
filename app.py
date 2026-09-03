import sqlite3
from google import genai
import pandas as pd
import streamlit as st

if "GEMINI_API_KEY" in st.secrets:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
else:
    st.error("GEMINI_API_KEY missing from Streamlit Secrets.")
    st.stop()

st.set_page_config(page_title="Church Farm Weather", layout="wide")
st.title("Church Farm School Weather Dashboard")

# 1. Fetch saved records from SQLite (Auto-detect table name)
conn = sqlite3.connect("weather.db")
try:
    # Find all table names in the uploaded database
    tables_df = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table';", conn)
    
    if not tables_df.empty:
        # Automatically select the first table found (e.g. daily_weather, weather, data)
        table_name = tables_df["name"].iloc[0]
        df = pd.read_sql_query(f'SELECT * FROM "{table_name}"', conn)
    else:
        st.warning("The database file was found, but it contains no data tables.")
        df = pd.DataFrame()
except Exception as e:
    st.error(f"Error reading database: {e}")
    df = pd.DataFrame()
finally:
    conn.close()

# 2. Tabbed Layout Architecture
tab_live, tab_charts, tab_ai = st.tabs(["⚡ Live Summary", "📊 Interactive Trends", "🤖 AI Assistant"])

# TAB 1: Live View (Fast Load)
with tab_live:
    if not df_clean.empty:
        latest = df_clean.iloc[-1]
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Temperature", f"{latest.get('temp_current', 0)} °F")
        c2.metric("Humidity", f"{latest.get('humidity', 0)} %")
        c3.metric("Wind Speed", f"{latest.get('wind_speed', 0)} mph")
        c4.metric("Barometer", f"{latest.get('bar_pressure', 0)} inHg")
        c5.metric("Rainfall", f"{latest.get('rain_total', 0)} in")
        
        st.subheader("Recent Activity (Last 30 Days)")
        df_recent = df_clean.tail(30)
        st.line_chart(df_recent.set_index("date_dt")[["temp_current", "humidity"]])
    else:
        st.info("No records found.")

# TAB 2: On-Demand Historical Charts
with tab_charts:
    st.subheader("Historical Weather Explorer")
    if not df_clean.empty:
        col_select, days_select = st.columns([3, 1])
        
        with days_select:
            time_window = st.selectbox("Time Window", [30, 90, 365, "All History", "Custom"], index=0)
        
        # Handle Custom Range vs Preset Windows
        if time_window == "Custom":
            min_avail = df_clean["date_dt"].min().date()
            max_avail = df_clean["date_dt"].max().date()
            
            # Render date picker range control
            selected_dates = st.date_input(
                "Select Date Range",
                value=(min_avail, max_avail),
                min_value=min_avail,
                max_value=max_avail
            )
            
            # Ensure both start and end dates are selected before filtering
            if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
                start_d, end_d = selected_dates
                mask = (df_clean["date_dt"].dt.date >= start_d) & (df_clean["date_dt"].dt.date <= end_d)
                df_filtered = df_clean[mask].copy()
            else:
                df_filtered = df_clean.copy()
                
        elif time_window != "All History":
            days_count = int(time_window)
            max_date = df_clean["date_dt"].max()
            min_date = max_date - pd.Timedelta(days=days_count)
            df_filtered = df_clean[df_clean["date_dt"] >= min_date].copy()
        else:
            df_filtered = df_clean.copy()

        # Resample large data ranges to daily averages for fast browser rendering
        if len(df_filtered) > 500:
            df_filtered = (
                df_filtered.set_index("date_dt")
                .resample("D")
                .mean(numeric_only=True)
                .reset_index()
            )

        with col_select:
            selected_metrics = st.multiselect(
                "Select Metrics to Plot",
                options=["temp_current", "humidity", "wind_speed", "bar_pressure", "rain_total"],
                default=["humidity"]
            )

        if selected_metrics:
            st.line_chart(df_filtered.set_index("date_dt")[selected_metrics])
        
        with st.expander("View Data Table"):
            st.dataframe(df_filtered.sort_values(by="date_dt", ascending=False), width="stretch")
# TAB 3: AI Q&A Assistant
with tab_ai:
    st.subheader("Ask Questions & Generate Predictions")
    user_question = st.text_input(
        "Ask about weather history or request a forecast analysis:",
        placeholder="e.g., What was the average temperature in January 2024?"
    )
    
    show_debug = st.checkbox("Show calculated summary table sent to AI", value=True)

    if st.button("Submit Query") and user_question:
        if df_clean.empty:
            st.warning("No data available.")
        else:
            with st.spinner("Analyzing weather database..."):
                try:
                    df_ai = df_clean.copy()
                    df_ai["year_month"] = df_ai["date_dt"].dt.strftime("%Y-%m (%B %Y)")

                    # Aggregate monthly metrics safely
                    monthly_df = df_ai.groupby("year_month").agg(
                        avg_temp=("temp_current", "mean"),
                        max_temp=("temp_current", "max"),
                        min_temp=("temp_current", "min"),
                        total_rain=("rain_total", "sum"),
                        avg_humidity=("humidity", "mean")
                    ).round(1).reset_index()

                    # Extract requested year (e.g., "2024") to send ONLY relevant months to Gemini
                    import re
                    years_in_q = re.findall(r"\b(20\d\d)\b", user_question)
                    if years_in_q:
                        target_year = years_in_q[0]
                        filtered_df = monthly_df[monthly_df["year_month"].str.contains(target_year)]
                        if not filtered_df.empty:
                            monthly_df = filtered_df

                    monthly_summary_str = monthly_df.to_string(index=False)

                    if show_debug:
                        st.write("**Data table passed to Gemini:**")
                        st.dataframe(monthly_df)

                    client = genai.Client(api_key=GEMINI_API_KEY)
                    prompt = (
                        "You are an expert weather data analyst for Church Farm School in Pennsylvania.\n"
                        "Answer the user's question using ONLY the pre-calculated monthly table below.\n"
                        "Locate the target month/year row and state the exact numbers directly.\n\n"
                        f"MONTHLY STATS TABLE:\n{monthly_summary_str}\n\n"
                        f"User Question: {user_question}"
                    )

                    response = client.models.generate_content(model="gemini-3.6-flash", contents=prompt)
                    st.markdown("**Answer:**")
                    st.write(response.text)
                except Exception as e:
                    st.error(f"Error answering question: {e}")
