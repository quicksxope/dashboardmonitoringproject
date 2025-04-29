import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import unicodedata
import re

def clean_text(x):
    if pd.isna(x):
        return ''
    x = unicodedata.normalize('NFKD', str(x)).encode('ascii', 'ignore').decode('utf-8')
    x = re.sub(r'\s+', ' ', x)
    return x.strip().upper()

st.set_page_config(page_title="📊 PT INCA Dashboard", layout="wide")

# Mobile styling
st.markdown("""
<style>
@media (max-width: 768px) {
    .element-container {
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
    }
    div[data-testid="column"] > div {
        margin-bottom: 1rem;
    }
    h2 {
        font-size: 1.4rem !important;
    }
    .stMarkdown > div {
        font-size: 0.95rem;
    }
}
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data(file):
    df = pd.read_excel(file, sheet_name="BASE DATA (wajib update)")
    df.columns = df.columns.str.strip()
    for col in ['KONTRAK', 'JENIS PEKERJAAN', 'STATUS']:
        if col in df.columns:
            df[col] = df[col].apply(clean_text)
    df['% COMPLETE'] = df['% COMPLETE'].apply(lambda x: x * 100 if x <= 1 else x)
    return df

def card(title, value, sub, icon="✅", bg="#ffffff"):
    return f"""
    <div style="padding:1rem; background:{bg}; border-radius:1rem; box-shadow:0 2px 6px rgba(0,0,0,0.06); text-align:center">
        <div style="font-size:1.5rem;">{icon}</div>
        <div style="font-size:1.2rem; font-weight:600">{title}</div>
        <div style="font-size:2rem; font-weight:700; margin:0.3rem 0;">{value}</div>
        <div style="color:gray">{sub}</div>
    </div>
    """

def main():
    st.markdown("<h2 style='margin-bottom: 1rem;'>📋 Project Monitoring Dashboard</h2>", unsafe_allow_html=True)
    uploaded_file = st.sidebar.file_uploader("📂 Upload Excel File", type="xlsx")
    if not uploaded_file:
        st.warning("Please upload an Excel file to continue.")
        return

    original_df = load_data(uploaded_file)
    df = original_df.copy()

    kontrak_opts = ['All'] + sorted(original_df['KONTRAK'].dropna().unique())
    selected_kontrak = st.sidebar.selectbox("Filter by KONTRAK", kontrak_opts)

    filter_columns = [col for col in df.columns if col not in ['KONTRAK', 'NO']]
    selected_filter_col = st.sidebar.selectbox("Filter Column", filter_columns)
    filter_values = ['All'] + sorted(original_df[selected_filter_col].dropna().unique())
    selected_filter_val = st.sidebar.selectbox("Select Value", filter_values)

    if selected_kontrak != 'All':
        df = df[df['KONTRAK'] == selected_kontrak]
    if selected_filter_val != 'All':
        df = df[df[selected_filter_col] == selected_filter_val]

    total_tasks = len(df)
    completed = (df['STATUS'] == 'SELESAI').sum()
    upcoming = (pd.to_datetime(df['PLAN END'], errors='coerce') - datetime.today()).dt.days.between(0, 7).sum()
    ongoing = (df['STATUS'] == 'DALAM PROSES').sum()
    pending = df[df['STATUS'].isin(['TUNDA', 'BELUM MULAI'])].shape[0]

    # Responsive 2x2 Cards
    row1c1, row1c2 = st.columns(2)
    with row1c1:
        st.markdown(card("Tasks Completed", f"{completed}/{total_tasks}", "Done", "✅", "#e3f2fd"), unsafe_allow_html=True)
    with row1c2:
        st.markdown(card("Upcoming Deadlines", upcoming, "Within 7 Days", "📅", "#f1f8e9"), unsafe_allow_html=True)

    row2c1, row2c2 = st.columns(2)
    with row2c1:
        st.markdown(card("In Progress", ongoing, "Active Tasks", "🚧", "#fff3e0"), unsafe_allow_html=True)
    with row2c2:
        st.markdown(card("Pending Issues", pending, "Status: Tunda/Belum Mulai", "⚠️", "#ffebee"), unsafe_allow_html=True)

    # --- Weighted Progress ---
    st.markdown("### 🎯 Weighted Progress by Bobot × % Complete (All Projects)")
    colA, colB = st.columns(2)
    for project, col in zip(['PROJECT 1 A', 'PROJECT 1 B'], [colA, colB]):
        proj_df = original_df[original_df['KONTRAK'] == project]
        if not proj_df.empty:
            weighted = (proj_df['BOBOT'] * proj_df['% COMPLETE']).sum()
            total_bobot = proj_df['BOBOT'].sum()
            progress = (weighted / total_bobot) if total_bobot else 0
            with col:
                st.markdown(f"**📌 {project}**")
                st.progress(int(progress))
                st.caption(f"Progress: **{progress:.2f}%**")
        else:
            with col:
                st.markdown(f"**📌 {project}**")
                st.info("No data available.")

    # --- Timeline & Task Table ---
    st.markdown("### 🗓 Project Timeline & Task Table")
    col_timeline, col_table = st.columns([1.3, 1])
    with col_timeline:
        if {'START', 'PLAN END'}.issubset(df.columns):
            df_timeline = df[['KONTRAK', 'START', 'PLAN END', 'STATUS']].dropna()
            df_timeline = df_timeline.rename(columns={'KONTRAK': 'Task'})
            color_map = {
                'SELESAI': 'green',
                'DALAM PROSES': 'blue',
                'TUNDA': 'orange',
                'BELUM MULAI': 'red'
            }
            fig = px.timeline(df_timeline, x_start='START', x_end='PLAN END', y='Task', color='STATUS', color_discrete_map=color_map)
            fig.update_yaxes(autorange="reversed")
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)

    with col_table:
        show_cols = ['KONTRAK', 'JENIS PEKERJAAN', 'STATUS', 'PLAN END', 'BOBOT']
        table_df = df[show_cols].rename(columns={
            'KONTRAK': 'Project',
            'JENIS PEKERJAAN': 'Task',
            'PLAN END': 'Due Date',
            'BOBOT': 'Weight'
        })
        st.dataframe(table_df, use_container_width=True, height=350)

   # --- Status Pie & Pending Chart ---
    st.markdown("### 📊 Task Distribution & Issues")
    c1, c2 = st.columns(2)

    with c1:
        status_counts = df['STATUS'].value_counts().reset_index()
        status_counts.columns = ['Status', 'Count']
        fig_status = px.pie(
            status_counts, names='Status', values='Count', hole=0.4,
            title="Status Breakdown",
            color='Status',
            color_discrete_map=color_map
        )
        st.plotly_chart(fig_status, use_container_width=True)

    with c2:
        pending_df = df[df['STATUS'].isin(['TUNDA', 'BELUM MULAI'])]  # Combined logic
        if not pending_df.empty:
            pending_count = pending_df['KONTRAK'].value_counts().reset_index()
            pending_count.columns = ['KONTRAK', 'Pending Count']
            fig_pending = px.bar(
                pending_count,
                x='Pending Count',
                y='KONTRAK',
                orientation='h',
                text='Pending Count',
                title="Projects with Pending Tasks",
                color='Pending Count',
                color_continuous_scale='Oranges'
            )
            fig_pending.update_layout(
                yaxis_title="Project",
                xaxis_title="Pending Tasks",
                height=400,
                margin=dict(l=40, r=10, t=40, b=40)
            )
            st.plotly_chart(fig_pending, use_container_width=True)
        else:
            st.info("No 'Tunda' or 'Belum Mulai' tasks to display.")


    # --- Late Tasks Section ---
    st.markdown("### 🕰 Overdue Tasks")
    late_df = df[(pd.to_datetime(df['PLAN END'], errors='coerce') < datetime.today()) & (df['STATUS'] != 'SELESAI')]
    late_df['LATE DAYS'] = (datetime.today() - pd.to_datetime(late_df['PLAN END'], errors='coerce')).dt.days

    if not late_df.empty:
        total_late_tasks = len(late_df)
        total_late_days = late_df['LATE DAYS'].sum()

        rowL1, rowL2 = st.columns(2)
        with rowL1:
            st.markdown(card("Late Tasks", f"{total_late_tasks} tasks", "Tasks overdue", "⏳", "#ffebee"), unsafe_allow_html=True)
        with rowL2:
            st.markdown(card("Total Late Days", f"{total_late_days}", "Total days overdue", "⚠️", "#ffe0e0"), unsafe_allow_html=True)

        late_df_display = late_df[['KONTRAK', 'JENIS PEKERJAAN', 'LATE DAYS']]
        late_df_display = late_df_display.rename(columns={
            'KONTRAK': 'Project',
            'JENIS PEKERJAAN': 'Task',
            'LATE DAYS': 'Days Late'
        })
        st.dataframe(late_df_display, use_container_width=True, height=350)
    else:
        st.info("No overdue tasks found.")

    st.success("✅ Dashboard rendered successfully.")

if __name__ == "__main__":
    main()
