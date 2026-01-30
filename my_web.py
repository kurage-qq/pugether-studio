import streamlit as st
from PIL import Image, PngImagePlugin
import json
import io
import zipfile
import re

# --- 1. 苹果风格页面设置 ---
st.set_page_config(page_title="Pugether Studio", page_icon="🔧", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #F5F5F7; }
    .main .block-container {
        background-color: white;
        padding: 3rem;
        border-radius: 24px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.05);
        margin-top: 2rem;
    }
    [data-testid="stHeader"], [data-testid="stSidebar"] { display: none; }
    .stButton>button {
        background-color: #0071E3;
        color: white;
        border-radius: 12px;
        border: none;
        padding: 0.5rem 2rem;
        font-weight: 500;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background-color: #0077ED;
        box-shadow: 0 4px 12px rgba(0,113,227,0.3);
    }
    h1 { font-family: "SF Pro Display", Arial; font-weight: 600; color: #1D1D1F; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

st.title("Pugether Studio")
tabs = st.tabs(["🧩批量拼图", "🔩快速拆图"])

def 自然排序(text):
    return [int(c) if c.isdigit() else c.lower() for c in re.split('([0-9]+)', text)]

# --- 拼图区 (已有的) ---
with tabs[0]:
    st.markdown("### 上传素材")
    files = st.file_uploader("将图片拖入此处", type=["png", "jpg", "jpeg"], accept_multiple_files=True, label_visibility="collapsed")
    direction = st.segmented_control("拼接方向", ["左右拼", "上下拼"], default="左右拼")
    
    if files:
        sorted_files = sorted(files, key=lambda x: 自然排序(x.name))
        st.caption(f"已选 {len(sorted_files)} 张图片")
        if st.button("开始拼图"):
            progress_bar = st.progress(0)
            zip_buffer = io.BytesIO()
            total_pairs = len(sorted_files) // 2
            if total_pairs > 0:
                with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED) as zip_file:
                    for i in range(0, total_pairs * 2, 2):
                        f1, f2 = sorted_files[i], sorted_files[i+1]
                        img1, img2 = Image.open(f1).convert("RGBA"), Image.open(f2).convert("RGBA")
                        info = {"w1": img1.width, "h1": img1.height, "w2": img2.width, "h2": img2.height, "dir": direction}
                        if direction == "左右拼":
                            h = max(img1.height, img2.height)
                            canvas = Image.new('RGBA', (img1.width + img2.width, h), (255, 255, 255, 0))
                            canvas.paste(img1, (0, 0)); canvas.paste(img2, (img1.width, 0))
                        else:
                            w = max(img1.width, img2.width)
                            canvas = Image.new('RGBA', (w, img1.height + img2.height), (255, 255, 255, 0))
                            canvas.paste(img1, (0, 0)); canvas.paste(img2, (0, img1.height))
                        meta = PngImagePlugin.PngInfo()
                        meta.add_text("recipe", json.dumps(info))
                        buf = io.BytesIO()
                        canvas.save(buf, format="PNG", pnginfo=meta)
                        zip_file.writestr(f"Pic_{i//2 + 1}.png", buf.getvalue())
                        progress_bar.progress((i + 2) / (total_pairs * 2))
                st.success("处理完成")
                st.download_button("下载 Pic.zip", data=zip_buffer.getvalue(), file_name="Pic.zip")

# --- 拆图区 (新增了进度条) ---
with tabs[1]:
    st.markdown("### 还原原图")
    c_files = st.file_uploader("上传拼好的图片", type=["png"], accept_multiple_files=True, label_visibility="collapsed", key="unzip")
    
    if c_files and st.button("立即拆分", key="unzip_btn"):
        # --- 这里增加了进度提示 ---
        progress_bar_u = st.progress(0)
        status_text_u = st.empty()
        
        zip_buffer = io.BytesIO()
        total_files = len(c_files)
        
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED) as zip_file:
            for idx, f in enumerate(c_files):
                # 更新文字，告诉奶奶正在拆哪一张
                status_text_u.text(f"正在拆解第 {idx + 1}/{total_files} 张: {f.name}")
                
                img = Image.open(f)
                if "recipe" in img.info:
                    recipe = json.loads(img.info["recipe"])
                    if recipe["dir"] == "左右拼":
                        res1 = img.crop((0, 0, recipe["w1"], recipe["h1"]))
                        res2 = img.crop((recipe["w1"], 0, recipe["w1"] + recipe["w2"], recipe["h2"]))
                    else:
                        res1 = img.crop((0, 0, recipe["w1"], recipe["h1"]))
                        res2 = img.crop((0, recipe["h1"], recipe["w2"], recipe["h1"] + recipe["h2"]))
                    
                    b1, b2 = io.BytesIO(), io.BytesIO()
                    res1.save(b1, format="PNG"); res2.save(b2, format="PNG")
                    zip_file.writestr(f"Restored_{f.name}_A.png", b1.getvalue())
                    zip_file.writestr(f"Restored_{f.name}_B.png", b2.getvalue())
                else:
                    st.error(f"跳过文件 {f.name}：它好像不是从这个工作室拼出来的哦！")
                
                # 推进进度条
                progress_bar_u.progress((idx + 1) / total_files)
        
        status_text_u.text("✨ 拆分任务全部完成！")
        st.success("处理完成")
        st.download_button("下载 Pic_restored.zip", data=zip_buffer.getvalue(), file_name="Pic_restored.zip")
