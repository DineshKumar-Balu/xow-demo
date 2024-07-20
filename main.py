import cv2
import easyocr
import pandas as pd
import re
import streamlit as st
import os
import subprocess
from datetime import datetime

base_dir = os.path.dirname(os.path.abspath(__file__))

# Set FFmpeg path
ffmpeg_path = os.path.join(base_dir, 'ffmpeg', 'ffmpeg.exe')

# Initialize EasyOCR reader
reader = easyocr.Reader(['en'])

def convert_to_h264(input_video_path, output_video_path):   
    command = [
        ffmpeg_path, '-y',
        '-i', input_video_path,
        '-c:v', 'libx264',
        output_video_path
    ]
    try:
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError as e:
        st.error(f"Error converting video: {e}")

def get_time_from_frame(img):
    text = reader.readtext(img, detail=0)  # Get the text from the image
    text = ' '.join(text)
    pattern = re.compile(r'\d{2}:\d{2}:\d{2}')
    res = pattern.search(text)
    return res.group(0) if res else None

def get_initial_time(video_path):
    vid = cv2.VideoCapture(video_path)
    if not vid.isOpened():
        st.error("Error opening video file.")
        return None
    vid.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Start at the first frame
    is_success, img = vid.read()
    vid.release()
    return get_time_from_frame(img) if is_success else None

def get_video_end_time(video_path):
    vid = cv2.VideoCapture(video_path)
    if not vid.isOpened():
        st.error("Error opening video file.")
        return None
    total_frames = int(vid.get(cv2.CAP_PROP_FRAME_COUNT))
    vid.set(cv2.CAP_PROP_POS_FRAMES, total_frames - 2)  # End at the second-to-last frame
    is_success, img = vid.read()
    vid.release()
    return get_time_from_frame(img) if is_success else None

def main():
    st.set_page_config(page_title="Video Player", page_icon="📹", layout="centered")

    uploaded_file = st.file_uploader("Upload a video file (MP4, AVI, MOV)", type=["mp4", "avi", "mov"])

    if uploaded_file:
        os.makedirs("./assets", exist_ok=True)
        video_path = "./assets/out.mp4"
        h264_video_path = "./assets/out_h264.mp4"

        with open(video_path, 'wb') as vid:
            vid.write(uploaded_file.read())

        convert_to_h264(video_path, h264_video_path)

        uploaded_csv = st.file_uploader("Upload a CSV file", type=["csv"])

        if 'jump_time_input' not in st.session_state:
            st.session_state.jump_time_input = "00:00:00"
        if 'previous_display' not in st.session_state:
            st.session_state.previous_display = None

        if uploaded_csv:
            df = pd.read_csv(uploaded_csv)
            initial_time = get_initial_time(h264_video_path)
            end_time = get_video_end_time(h264_video_path)
            end_time_str = end_time
            initial_time_dt = datetime.strptime(initial_time, '%H:%M:%S') if initial_time else None

            if not df.empty:
                col1, col2 = st.columns(2)
                with col1:
                    column = st.selectbox('Select a column', df.columns.tolist(), index=0)

                with col2:
                    display_options = ["Select"] + df[column].astype(str).tolist()
                    display = st.selectbox("Select a value", display_options, index=0)

                if column and display != "Select":
                    if st.session_state.previous_display != display:
                        st.session_state.jump_time_input = "00:00:00"
                        st.session_state.previous_display = display
                        st.experimental_rerun()

                    filtered_df = df[df[column].astype(str) == display]
                    st.write("Filtered Data:", filtered_df)

                    if not filtered_df.empty:
                        date_time_str = filtered_df["DATE AND TIME"].iloc[0]

                        # Extract time and convert to seconds
                        time_parts = date_time_str.split()
                        if len(time_parts) > 0:
                            time_str = time_parts[-1]

                            try:
                                extracted_time_dt = datetime.strptime(time_str, '%H:%M:%S')

                                # Ensure the extracted time is within the valid range
                                if initial_time_dt and end_time and initial_time_dt <= extracted_time_dt <= datetime.strptime(end_time_str, '%H:%M:%S'):
                                    extracted_time_seconds = (extracted_time_dt - initial_time_dt).total_seconds()
                                    jump_seconds = 0
                                    if initial_time and end_time:
                                        c1, c2 = st.columns(2)
                                        with c1:
                                            st.write("Initial Time from Video:", initial_time)
                                        with c2:
                                            st.write("End Time from Video:", end_time)

                                        col1, col2 = st.columns(2)
                                        with col1:
                                            st.write("**Start Time**")
                                            start_time_input = st.text_input("", initial_time, key="start_time")
                                        with col2:
                                            st.write("**Jump Time**")
                                            st.session_state.jump_time_input = st.text_input(
                                                "",
                                                st.session_state.jump_time_input,
                                                key="jump_time"
                                            )

                                        jump_time_dt = datetime.strptime(
                                            st.session_state.jump_time_input, '%H:%M:%S'
                                        ) if st.session_state.jump_time_input else 0

                                        if jump_time_dt and jump_time_dt >= extracted_time_dt:
                                            jump_seconds = (jump_time_dt - extracted_time_dt).total_seconds()

                                    # Play video from extracted time if video exists
                                    if os.path.exists(h264_video_path):
                                        st.video(h264_video_path, start_time=extracted_time_seconds + jump_seconds,
                                                 format='video/mp4', autoplay=True)
                                    else:
                                        st.write("Error: Video file not found at:", h264_video_path)
                                else:
                                    st.write("Extracted time is out of the valid range. Playing from the start.")
                            except Exception as e:
                                st.write("Error parsing time:", e, "Playing from the start.")
                        else:
                            st.write("Time string is empty. Playing from the start.")
                    else:
                        st.write("No matching value found in the selected column. Playing from the start.")
            else:
                st.write("CSV file is empty.")
    else:
        st.write("Upload a video file to start.")

if __name__ == "__main__":
    main()
