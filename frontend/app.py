import streamlit as st
import requests
import pandas as pd
import os
from app_config import AppConfig
from backend_func import *


os.makedirs(AppConfig.TEMP_DOWNLOAD_FOLDER, exist_ok=True)

st.set_page_config(
    page_title="Анализ заполненности зала ",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "processing" not in st.session_state:
    st.session_state.processing = False
if "last_request_id" not in st.session_state:
    st.session_state.last_request_id = None

st.title("Вариант 24. Анализ заполненности зала")

value = st.pills(
    "Выберите действие:",
    ["Загрузчик", "История", "Отчет"],
    selection_mode="single",
    default="Загрузчик",
)

if value == "Загрузчик":
    st.header("Загрузить и обработать фото/видео")

    uploaded_file = st.file_uploader(
        "Прикрепите фото/видео файл",
        type=["jpg", "jpeg", "png", "mp4", "avi", "mov"],
        key="file_uploader",
    )

    if uploaded_file is not None:
        file_type = uploaded_file.type.split("/")[0]
        st.subheader("Загруженный файл")
        if file_type == "image":
            st.image(uploaded_file, use_container_width=True)
        elif file_type == "video":
            st.video(uploaded_file)

    if st.button(
        "Обработка файла",
        key="process_btn",
        disabled=st.session_state.processing or uploaded_file is None,
    ):
        st.session_state.processing = True
        try:
            result_data, result_response = process_and_display(uploaded_file)
            if result_data and result_response:
                display_result(result_response, result_data["stats"])
        finally:
            st.session_state.processing = False

if value == "История":
    st.header("История")

    if st.button("Обновить", key="refresh_history"):
        history = get_history()

        if not history:
            st.warning("История пуста")
        else:
            df = pd.DataFrame(history)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp", ascending=False)

            st.dataframe(
                df[["request_id", "timestamp", "original_file"]],
                use_container_width=True,
                hide_index=True,
            )

            selected_request = st.selectbox(
                "Выберите для подробного просмотра",
                df["request_id"].tolist(),
                key="request_selector",
            )

            if selected_request:
                selected = df[df["request_id"] == selected_request].iloc[0].to_dict()

                try:
                    result_response = requests.get(
                        f"{AppConfig.BACKEND_URL}/result/{selected_request}",
                        stream=True,
                    )

                    if result_response.status_code == 200:
                        display_result(result_response, selected.get("stats"))
                    else:
                        st.warning("Нет результатов")
                except Exception as e:
                    st.error(f"Ошибка: {str(e)}")

if value == "Отчет":
    st.header("Формирование отчета")

    if st.button("Составить отчет", key="generate_report"):
        with st.spinner("Загрузка..."):
            report_path = generate_report()

            if report_path:
                df = pd.read_excel(report_path)
                st.dataframe(df, use_container_width=True, hide_index=True)

                with open(report_path, "rb") as f:
                    st.download_button(
                        label="Скачать отчет",
                        data=f,
                        file_name="hall_occupancy_report.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )

                try:
                    os.remove(report_path)
                except:
                    pass

st.markdown(
    """
    <style>
        .stButton button {
            width: 100%;
        }
        .stDownloadButton button {
            width: 100%;
            background-color: #4CAF50;
            color: white;
        }
        div[data-testid="stMetric"] {
            text-align: center;
        }
    </style>
""",
    unsafe_allow_html=True,
)
