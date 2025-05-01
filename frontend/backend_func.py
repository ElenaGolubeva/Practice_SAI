import streamlit as st
import requests
from app_config import AppConfig
import time
import os


def process_and_display(file):
    try:
        with st.spinner("Обработка файла..."):
            response = requests.post(f"{AppConfig.BACKEND_URL}/process/", files={"file": file})
            response.raise_for_status()
            result = response.json()
            request_id = result["request_id"]
            st.session_state.last_request_id = request_id
            max_attempts = 20
            result_response = None
            for _ in range(max_attempts):
                try:
                    result_response = requests.get(
                        f"{AppConfig.BACKEND_URL}/result/{request_id}", stream=True
                    )
                    if result_response.status_code == 200:
                        break
                except:
                    pass
                time.sleep(0.5)
            else:
                st.error(
                    "Обработка результатов занимает больше времени, чем ожидалось."
                )
                return None, None

            return result, result_response
    except Exception as e:
        st.error(f"Ошибка: {str(e)}")
        return None, None


def display_result(result_response, stats):
    if result_response is None:
        st.warning("Нет результатов для отображения")
        return

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Результат обработки")
        try:
            if "image" in result_response.headers.get("content-type", ""):
                st.image(result_response.content, use_container_width=True)
            elif "video" in result_response.headers.get("content-type", ""):
                video_bytes = result_response.content
                st.video(video_bytes)
        except Exception as e:
            st.error(f"Ошибка в отображении результатов: {str(e)}")

    with col2:
        if stats:
            display_stats(stats)


def display_stats(stats):
    st.subheader("Статистика")

    total = stats.get("total_chairs", 0)
    free = stats.get("free_chairs", stats.get("total_free_chairs", 0))
    occupied = stats.get("occupied_chairs", stats.get("total_occupied_chairs", 0))

    if total > 0:
        st.metric("Всего стульев", total)
        st.metric("Свободные", free, delta=f"{(free/total)*100:.1f}%")
        st.metric("Занятые", occupied, delta=f"{(occupied/total)*100:.1f}%")
    else:
        st.warning("На фото/видео не обнаружены стулья.")


def get_history():
    try:
        response = requests.get(f"{AppConfig.BACKEND_URL}/history/")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Ошибка в отображении истории: {str(e)}")
        return []


def generate_report():
    try:
        response = requests.get(f"{AppConfig.BACKEND_URL}/report/")
        response.raise_for_status()

        report_path = os.path.join(AppConfig.TEMP_DOWNLOAD_FOLDER, "report.xlsx")
        with open(report_path, "wb") as f:
            f.write(response.content)

        return report_path
    except Exception as e:
        st.error(f"Ошибка в генерации отчета: {str(e)}")
        return None

