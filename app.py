import sqlite3
from google import genai
import pandas as pd
import streamlit as st

# Insert your actual Google Gemini API key here
GEMINI_API_KEY = "insert key here"

st.set_page_config(page_title="Church Farm Weather", layout="wide")
st.title("Church Farm School Weather Dashboard")

# 1. Fetch saved records from SQLite
conn = sqlite3.connect("weather.db")
df = pd.read_sql_query("SELECT * FROM daily_weather", conn)
conn.close()

# 2. Live KPI Summary Cards
if not df.empty:
    latest = df.iloc[-1]
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Temperature", f"{latest.get('temp_current', 0)} °F")
    col2.metric("Humidity", f"{latest.get('humidity', 0)} %")
    col3.metric("Wind Speed", f"{latest.get('wind_speed', 0)} mph")
    col4.metric("Barometer", f"{latest.get('bar_pressure', 0)} inHg")
    col5.metric("Rain Today", f"{latest.get('rain_total', 0)} in")

st.divider()

# 3. Station Data Trends
st.subheader("Station Data Log")
if not df.empty:
    st.write("**Temperature, Humidity, & Wind Speed**")
    st.line_chart(
        df.set_index("date")[["temp_current", "humidity", "wind_speed"]]
    )

    st.write("**Daily Precipitation (Inches)**")
    st.bar_chart(df.set_index("date")["rain_total"])

    st.dataframe(
        df.sort_values(by="date", ascending=False), use_container_width=True
    )
else:
    st.info("No records logged yet. Run database.py or import_csv.py first.")

st.divider()

# 4. Interactive Q&A Assistant
st.subheader("Ask Questions About Station History")
user_question = st.text_input(
    "Ask a question about your weather history:",
    placeholder="e.g., What was the average temperature in August? Or how much rain fell on August 20 in past years?",
)

if st.button("Ask Assistant") and user_question:
    if df.empty:
        st.warning("No historical data available to query.")
    else:
        with st.spinner("Analyzing weather database..."):
            try:
                client = genai.Client(api_key=GEMINI_API_KEY)
                full_data_str = df.to_string(index=False)

                prompt = (
                    "You are an expert meteorological data analyst for Church Farm School.\n"
                    "Answer the user's question accurately using ONLY the provided daily weather dataset.\n"
                    "Perform any necessary calculations (averages, historical comparisons, totals, min/max) based on the data rows.\n\n"
                    f"Dataset:\n{full_data_str}\n\n"
                    f"User Question: {user_question}"
                )

                response = client.models.generate_content(
                    model="gemini-3.6-flash", contents=prompt
                )

                st.markdown("**Answer:**")
                st.write(response.text)
            except Exception as e:
                st.error(f"Error answering question: {e}")

st.divider()

# 5. AI Forecast Analysis
st.subheader("AI Microclimate Predictions")
if st.button("Generate Weather Predictions"):
    with st.spinner("Analyzing weather patterns with Gemini..."):
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            recent_data = df.tail(30).to_string()

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