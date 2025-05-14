import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="📁 Contract Summary Dashboard", layout="wide")
from auth import require_login
require_login()
st.title("📁 Contract Summary Dashboard")

# --- Section Card Function ---
def section_card(title=None):
    section = st.container()
    section_id = f"section_{title.replace(' ', '_').lower() if title else 'no_title'}"
    if title:
        section.markdown(f"""
        <div id=\"{section_id}_header\" style=\"background: linear-gradient(to right, #3498db, #1abc9c); color: white; padding: 12px 15px;                 border-radius: 10px 10px 0 0; margin-bottom: 0; font-weight: 600; font-size: 1.2rem;                text-shadow: 1px 1px 2px rgba(0,0,0,0.3); box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);\">
            {title}
        </div>
        """, unsafe_allow_html=True)
    return section

# --- Metric Card Function ---
def metric_card(title, value, sub, icon="✅", bg="#2196f3"):
    gradient = f"linear-gradient(135deg, {bg}, {bg})"
    text_color = "#ffffff"
    sub_color = "#e0e0e0"
    shadow_color = "rgba(0, 0, 0, 0.3)"
    return f"""
    <div class=\"metric-card\" style=\"padding:1.2rem; background:{gradient}; border-radius:1rem; box-shadow:0 3px 10px {shadow_color}; text-align:center; margin-bottom:1rem; height:100%; width:100%; max-width:100%; border:none !important; outline:none !important;\">
        <div style=\"font-size:1.5rem; margin-bottom:0.3rem;\">{icon}</div>
        <div style=\"font-size:1.2rem; font-weight:600; color:{text_color}; margin-bottom:0.5rem;\">{title}</div>
        <div style=\"font-size:calc(1.5rem + 0.5vw); font-weight:700; color:{text_color}; margin:0.6rem 0;\">{value}</div>
        <div style=\"color:{sub_color}; font-size:0.9rem;\">{sub}</div>
    </div>
    """

# --- Upload File ---
uploaded_file = st.file_uploader("📂 Upload Contract Excel File", type="xlsx")

if uploaded_file:
    df_raw = pd.read_excel(uploaded_file, sheet_name='Kontrak', skiprows=7)
    df_raw.dropna(axis=0, how='all', inplace=True)
    df_left = df_raw.iloc[:, :13]
    header_row = df_left.iloc[0]
    df = df_left[1:].copy()
    df.columns = header_row
    df.columns = [str(col).strip() for col in df.columns]

    df.rename(columns={
        'Start Date': 'START',
        'End Date': 'END',
        'TIME GONE %': 'PROGRESS'
    }, inplace=True)

    df['START'] = pd.to_datetime(df['START'], errors='coerce')
    df['END'] = pd.to_datetime(df['END'], errors='coerce')
    df['DURATION'] = (df['END'] - df['START']).dt.days
    df['PROGRESS'] = pd.to_numeric(df['PROGRESS'], errors='coerce')
    df = df[df['START'].notnull() & df['END'].notnull() & (df['END'] >= df['START'])]

    # Metrics
    total_contracts = len(df)
    active_contracts = df[df['STATUS'] == 'ACTIVE'].shape[0]
    non_active_contracts = df[df['STATUS'] != 'ACTIVE'].shape[0]
    avg_duration = df['DURATION'].mean()
    min_duration = df['DURATION'].min()
    max_duration = df['DURATION'].max()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(metric_card("Total Contracts", total_contracts, "All listed contracts", "📦"), unsafe_allow_html=True)
    with col2:
        st.markdown(metric_card("Active Contracts", active_contracts, "Currently ongoing", "✅"), unsafe_allow_html=True)
    with col3:
        st.markdown(metric_card("Non-Active Contracts", non_active_contracts, "Finished or inactive", "🛑"), unsafe_allow_html=True)

    col4, col5, col6 = st.columns(3)
    with col4:
        st.markdown(metric_card("Avg Duration", f"{avg_duration:.0f} days", "Average contract period", "⏱️"), unsafe_allow_html=True)
    with col5:
        st.markdown(metric_card("Min Duration", f"{min_duration} days", "Shortest contract", "📉"), unsafe_allow_html=True)
    with col6:
        st.markdown(metric_card("Max Duration", f"{max_duration} days", "Longest contract", "📈"), unsafe_allow_html=True)

    # --- Time-Gone Based Progress ---
    with section_card("📈 Project Progress Categories (Based on Time Elapsed)"):
        today = pd.Timestamp.today()
        df['TIME_GONE'] = ((today - df['START']) / (df['END'] - df['START'])).clip(0, 1) * 100

        bins = [-1, 30, 50, 80, 100]
        labels = ['<30%', '30-50%', '50-80%', '>80%']
        df['TIME_GONE_CAT'] = pd.cut(df['TIME_GONE'], bins=bins, labels=labels)

        progress_counts = df['TIME_GONE_CAT'].value_counts().sort_index().reset_index()
        progress_counts.columns = ['Progress Range', 'Count']
        fig_progress = px.bar(progress_counts, x='Progress Range', y='Count', color='Progress Range',
                              title="Project Progress by Time Elapsed", text='Count')
        st.plotly_chart(fig_progress, use_container_width=True)

    # --- Status Pie Chart ---
    with section_card("📊 Contract Status Distribution"):
        status_counts = df['STATUS'].value_counts().reset_index()
        status_counts.columns = ['Status', 'Count']
        fig_status = px.pie(status_counts, names='Status', values='Count', hole=0.4)
        st.plotly_chart(fig_status, use_container_width=True)

    # --- Gantt Chart ---
    with section_card("📆 Gantt Chart - Contract Timelines"):
        df_sorted = df.sort_values('START')
        fig_gantt = px.timeline(
            df_sorted,
            x_start='START',
            x_end='END',
            y='KONTRAK',
            color='STATUS',
            hover_data=['DURATION', 'PROGRESS', 'TIME_GONE'],
            title="Contract Gantt Timeline"
        )
        fig_gantt.update_yaxes(autorange="reversed")
        st.plotly_chart(fig_gantt, use_container_width=True)

    # --- Data Table ---
    with section_card("📋 Contract Table"):
        st.dataframe(df[['KONTRAK', 'START', 'END', 'DURATION', 'STATUS', 'PROGRESS', 'TIME_GONE']].sort_values('END'), use_container_width=True)

else:
    st.info("Upload an Excel file with a 'Kontrak' sheet to see the dashboard.")