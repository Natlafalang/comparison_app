import streamlit as st
import pandas as pd
import numpy as np
import io

# ------------------- Helper Functions (Adapted from your Colab script) ------------------------

def get_sheet_names(uploaded_file):
    """Get all sheet names from an uploaded Excel file."""
    if uploaded_file:
        try:
            # Create a BytesIO object to allow pandas to read the in-memory file
            file_buffer = io.BytesIO(uploaded_file.getvalue())
            xls = pd.ExcelFile(file_buffer, engine='openpyxl')
            return xls.sheet_names
        except Exception as e:
            st.error(f"Error reading sheet names from {uploaded_file.name}: {e}")
            return []
    return []


def load_dataframe_from_selected_sheets(uploaded_file, sheet_names_to_load, id_column, header_row=0):
    """Load a dataframe by concatenating specific sheets from an uploaded file."""
    try:
        file_buffer = io.BytesIO(uploaded_file.getvalue())
        xls = pd.ExcelFile(file_buffer, engine='openpyxl')
        all_dfs = []
        
        for sheet_name in sheet_names_to_load:
            if sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name, engine='openpyxl', header=header_row)
                if id_column in df.columns:
                    df[id_column] = df[id_column].astype(str).str.strip()  # Standardize
                    all_dfs.append(df)
                    st.info(f"Loaded data from sheet '{sheet_name}' of '{uploaded_file.name}' with {len(df)} rows.")
                else:
                    st.warning(f"Column '{id_column}' not found in sheet '{sheet_name}'. Skipping this sheet.")
            else:
                st.warning(f"Sheet '{sheet_name}' not found in '{uploaded_file.name}'. Skipping.")

        if not all_dfs:
            st.error(f"ID column '{id_column}' not found in any of the selected sheets. Please check your column name and sheet selections.")
            return pd.DataFrame()

        combined_df = pd.concat(all_dfs, ignore_index=True)
        return combined_df
    except Exception as e:
        st.error(f"Error loading '{uploaded_file.name}': {e}")
        return pd.DataFrame()


def find_duplicates(df1, df2, id_column_1, id_column_2, chunk_size=500):
    """Find duplicate IDs in two datasets using chunking and set lookup."""
    duplicates = []
    total = len(df1)
    progress_bar = st.progress(0)
    status_text = st.empty()

    # Use a set for fast lookup
    valid_ids_set = set(df2[id_column_2].dropna().astype(str).str.strip().tolist())
    status_text.info(f"Created a lookup set with {len(valid_ids_set)} unique IDs from the second file.")

    for start in range(0, total, chunk_size):
        end = min(start + chunk_size, total)
        chunk = df1.iloc[start:end].copy()
        chunk['Standard_ID'] = chunk[id_column_1].astype(str).str.strip()

        matched_chunk = chunk[chunk['Standard_ID'].isin(valid_ids_set)]

        if not matched_chunk.empty:
            enriched = matched_chunk.merge(
                df2,
                left_on='Standard_ID',
                right_on=id_column_2,
                how='left',
                suffixes=('_File1', '_File2')
            )
            duplicates.append(enriched)
        
        progress = (end / total)
        progress_bar.progress(progress)
        status_text.info(f"Processing... Checked {end} of {total} rows from the first file.")

    progress_bar.empty() # Clear the progress bar on completion
    status_text.empty()

    if duplicates:
        result = pd.concat(duplicates, ignore_index=True)
        st.success(f"✅ Comparison complete! Found {len(result)} duplicate records.")
        return result
    else:
        st.success("✅ Comparison complete! No duplicates were found.")
        return pd.DataFrame()


# -------------------- Streamlit App UI -----------------------------

st.set_page_config(layout="wide")
st.title("📂 Advanced Excel Duplicate Finder")
st.write("This tool finds records in 'File 1' that have a matching ID in 'File 2'.")
st.write("Based on your Colab script for comparing a waiting list against residential files.")

# --- Step 1: File Uploads ---
st.header("Step 1: Upload Your Excel Files")
col1, col2 = st.columns(2)
with col1:
    file1 = st.file_uploader("Upload File 1 (e.g., Waiting List)", type=['xlsx'])
with col2:
    file2 = st.file_uploader("Upload File 2 (e.g., Residential Allocations)", type=['xlsx'])

# --- Step 2: Configuration (dynamically appears after uploads) ---
if file1 and file2:
    st.header("Step 2: Configure Comparison")
    
    # Get all columns from the first row of each file for selection
    df1_cols = pd.read_excel(io.BytesIO(file1.getvalue()), nrows=1, engine='openpyxl').columns.tolist()
    df2_cols = pd.read_excel(io.BytesIO(file2.getvalue()), nrows=1, engine='openpyxl').columns.tolist()
    
    file1_sheets = get_sheet_names(file1)
    file2_sheets = get_sheet_names(file2)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader(f"'{file1.name}' Settings")
        file1_id_col = st.selectbox("Select ID Column for File 1", options=df1_cols, index=0)
        file1_selected_sheets = st.multiselect("Select Sheet(s) to process from File 1", options=file1_sheets, default=file1_sheets[0] if file1_sheets else [])

    with c2:
        st.subheader(f"'{file2.name}' Settings")
        file2_id_col = st.selectbox("Select ID Column for File 2", options=df2_cols, index=0)
        file2_selected_sheets = st.multiselect("Select Sheet(s) to process from File 2", options=file2_sheets, default=file2_sheets if file2_sheets else [])
        
    # --- Step 3: Run Comparison ---
    if st.button("🚀 Find Duplicates", type="primary"):
        if not file1_selected_sheets or not file2_selected_sheets:
            st.warning("Please select at least one sheet for each file.")
        else:
            with st.spinner("Loading data... This may take a moment."):
                df1 = load_dataframe_from_selected_sheets(file1, file1_selected_sheets, file1_id_col)
                df2 = load_dataframe_from_selected_sheets(file2, file2_selected_sheets, file2_id_col)
            
            if not df1.empty and not df2.empty:
                st.header("Processing and Finding Duplicates...")
                duplicates_df = find_duplicates(df1, df2, id_column_1=file1_id_col, id_column_2=file2_id_col)

                if not duplicates_df.empty:
                    st.header("Results: Duplicate Records Found")
                    st.dataframe(duplicates_df)
                    
                    # --- Download Button ---
                    csv = duplicates_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download Results as CSV",
                        data=csv,
                        file_name='duplicate_report.csv',
                        mime='text/csv',
                    )

else:
    st.info("Please upload both Excel files to begin.")