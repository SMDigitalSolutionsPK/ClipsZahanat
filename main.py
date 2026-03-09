import os
import streamlit as st
import yt_dlp
from yt_dlp.utils import download_range_func
import google.generativeai as genai
from moviepy import VideoFileClip

WORK_DIR = "workspace"
os.makedirs(WORK_DIR, exist_ok=True)


def format_time(seconds):
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"


def download_audio_only(url, output_filename):
    if os.path.exists(output_filename):
        os.remove(output_filename)
    ydl_opts = {'format': 'bestaudio/best', 'outtmpl': output_filename}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def download_clip_only(url, output_filename, start_sec, end_sec):
    if os.path.exists(output_filename):
        os.remove(output_filename)
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': output_filename,
        'download_ranges': download_range_func(None, [(start_sec, end_sec)]),
        'force_keyframes_at_cuts': True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def find_best_clips_cloud(audio_path, api_key):
    genai.configure(api_key=api_key)
    uploaded_file = genai.upload_file(path=audio_path)

    model = genai.GenerativeModel('gemini-2.5-flash')
    prompt = """
    You are an expert video editor. Listen to this audio track and find the top 3 most engaging continuous clips for viral shorts.
    Each clip MUST be between 15 and 60 seconds long.
    Return the result EXACTLY in this format, with no other text:
    Title: [Catchy Title 1]
    Start: [number]
    End: [number]
    ---
    Title: [Catchy Title 2]
    Start: [number]
    End: [number]
    ---
    Title: [Catchy Title 3]
    Start: [number]
    End: [number]
    """

    response = model.generate_content([prompt, uploaded_file])
    genai.delete_file(uploaded_file.name)

    clips = []
    blocks = response.text.strip().split('---')
    for block in blocks:
        lines = [line.strip() for line in block.strip().split('\n') if line.strip()]
        if len(lines) >= 3:
            try:
                title = lines[0].replace("Title:", "").strip()
                start = float(lines[1].replace("Start:", "").strip())
                end = float(lines[2].replace("End:", "").strip())
                clips.append({"title": title, "start": start, "end": end})
            except:
                continue
    return clips


def make_vertical_short(input_file, output_file):
    video = VideoFileClip(input_file)
    w, h = video.size
    
    # Calculate new width for 9:16 aspect ratio
    new_w = int(h * (9 / 16))
    
    # FFmpeg strictly requires even numbers for video dimensions
    if new_w % 2 != 0:
        new_w -= 1
        
    vertical_clip = video.cropped(
        x_center=w / 2,
        y_center=h / 2,
        width=new_w,
        height=h
    )
    
    vertical_clip.write_videofile(
        output_file, 
        codec="libx264", 
        audio_codec="aac",
        preset="ultrafast", 
        threads=4 
    )


st.set_page_config(page_title="Clips Zahanat Maker", layout="centered")
st.title("✂️ Clips Zahanat Maker")

if "clips" not in st.session_state:
    st.session_state.clips = []

video_link = st.text_input("Paste YouTube Link Here")
api_key = st.text_input("Paste your Google Gemini API Key", type="password")

if st.button("1. Analyze Video & Find Hooks"):
    if not video_link or not api_key:
        st.error("Please provide both a video link and a Google Gemini API key.")
    else:
        with st.status("Analyzing audio in the cloud...", expanded=True) as status:
            audio_file = f"{WORK_DIR}/temp_audio.m4a"

            st.write("Downloading audio only")
            download_audio_only(video_link, audio_file)

            st.write("Asking Gemini to find the top 3 hooks")
            st.session_state.clips = find_best_clips_cloud(audio_file, api_key)

            status.update(label="Analysis complete! Choose your favorite clip below.", state="complete")

if st.session_state.clips:
    st.write("### 🎯 Select a Clip to Generate")

    for i, clip in enumerate(st.session_state.clips):
        st.markdown(f"**Option {i + 1} {clip['title']}**")

        start_fmt = format_time(clip['start'])
        end_fmt = format_time(clip['end'])
        st.write(f"⏱️ Timestamp {start_fmt} to {end_fmt}")

        st.write("👀 **Preview this segment**")
        st.video(video_link, start_time=int(clip['start']))

        if st.button(f"Generate & Crop Clip {i + 1}", key=f"btn_{i}"):
            with st.status(f"Generating '{clip['title']}'...", expanded=True) as status:
                raw_video = f"{WORK_DIR}/temp_clip_{i}.mp4"
                final_short = f"{WORK_DIR}/final_short_{i}.mp4"

                st.write("Downloading ONLY the selected seconds")
                download_clip_only(video_link, raw_video, clip['start'], clip['end'])

                st.write("Cropping for mobile")
                make_vertical_short(raw_video, final_short)

                status.update(label="Video ready!", state="complete")

            st.success("Watch your final vertical short below!")
            st.video(final_short)

            with open(final_short, "rb") as file:
                st.download_button("💾 Download Final Short", data=file, file_name=f"Clips_Zahanat_Op{i + 1}.mp4",
                                   mime="video/mp4")
        st.divider()

