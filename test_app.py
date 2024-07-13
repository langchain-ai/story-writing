import streamlit as st
import streamlit as st 

st.set_page_config(layout="wide")

def main():
    st.title("Multiple Columns Example")

    # First set of columns
    col1, col2 = st.columns([1, 3])

    with col1:
        st.header("Column 1")
        st.write("Content for column 1")

    with col2:
        st.header("Column 2")
        st.write("Content for column 2")

    # Second set of columns
    col3, col4, col5 = st.columns([1, 1, 1])

    with col3:
        st.header("Column 3")
        st.write("Content for column 3")

    with col4:
        st.header("Column 4")
        st.write("Content for column 4")

    with col5:
        st.header("Column 5")
        st.write("Content for column 5")

if __name__ == "__main__":
    main()