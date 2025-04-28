import streamlit as st
import pandas as pd
import plotly.express as px

def main():
    # Title of the app
    st.title('Upload Excel File, Filter Data, and Visualize')

    # File uploader widget for uploading the Excel file
    uploaded_file = st.file_uploader("Choose an Excel file", type="xlsx")

    # Check if a file has been uploaded
    if uploaded_file is not None:
        # Read the uploaded Excel file
        xls = pd.ExcelFile(uploaded_file)

        # Get sheet names
        sheet_names = xls.sheet_names

        # Show available sheets in the sidebar
        st.sidebar.write("📑 Available Sheets:", sheet_names)

        # Let user select a sheet
        selected_sheet = st.sidebar.selectbox("Select a Sheet", sheet_names)

        # Read the selected sheet
        df = pd.read_excel(uploaded_file, sheet_name=selected_sheet)

        # Show available columns for filtering
        st.sidebar.write("📝 Available Columns for Filtering:")
        columns = df.columns.tolist()
        selected_column = st.sidebar.selectbox("Select a Column to Filter", columns)

        # Show unique values in the selected column to filter by
        unique_values = df[selected_column].dropna().unique()
        selected_value = st.sidebar.selectbox(f"Select a value for {selected_column}", unique_values)

        # Filter the dataframe based on the selected column and value
        filtered_df = df[df[selected_column] == selected_value]

        # Display the filtered DataFrame as a table in the Streamlit app
        st.write(f"Filtered Data (showing rows where '{selected_column}' = '{selected_value}'):")
        st.dataframe(filtered_df)

        # Add a download button for the filtered data
        csv = filtered_df.to_csv(index=False)
        st.download_button(label="Download Filtered Data", data=csv, file_name="filtered_data.csv", mime="text/csv")

        # Visualization 1: Pie Chart (for categorical data)
        if 'STATUS' in filtered_df.columns:
            status_counts = filtered_df['STATUS'].value_counts().reset_index()
            status_counts.columns = ['Status', 'Count']
            fig_pie = px.pie(status_counts, names='Status', values='Count', title='Status Distribution', 
                             color='Status', color_discrete_map={"Completed": "green", "In Progress": "orange", "Pending": "red"})
            st.plotly_chart(fig_pie)

        # Visualization 2: Bar Chart (for numerical data)
        if 'KONTRAK' in filtered_df.columns and 'SISA DURASI KONTRAK' in filtered_df.columns:
            task_counts = filtered_df.groupby('KONTRAK').size().reset_index(name='Task Count')
            fig_bar = px.bar(task_counts, x='KONTRAK', y='Task Count', title='Task Counts per Project', 
                             color='Task Count', color_continuous_scale='Viridis', labels={'Task Count': 'Number of Tasks'})
            st.plotly_chart(fig_bar)

        # Visualization 3: Scatter Plot (optional, if numerical data is present)
        if 'KONTRAK' in filtered_df.columns and 'SISA DURASI KONTRAK' in filtered_df.columns:
            fig_scatter = px.scatter(filtered_df, x='KONTRAK', y='SISA DURASI KONTRAK', color='STATUS', 
                                     title='Task Duration vs Project', 
                                     color_discrete_map={"Completed": "green", "In Progress": "orange", "Pending": "red"})
            st.plotly_chart(fig_scatter)

    else:
        st.write("Please upload an Excel file to display the data.")

if __name__ == "__main__":
    main()
