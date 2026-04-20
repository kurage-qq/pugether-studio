import streamlit as st
from PIL import Image, PngImagePlugin, ImageChops
import json
import io
import zipfile
import re
import numpy as np

# --- 1. 页面样式 ---
st.set_page_config(page_title="Pugether Studio", page_icon="🔧", layout="centered")

if 'p_clear_id' not in st.session_state: st.session_state.p_clear_id = 0
if 'u_clear_id' not in st.session_state: st.session_state.u_clear_id = 0

st.markdown("""
    <style>
    .stApp { background-color: #F5F5F7; }
    .main .block-container { background-color: rgba(255, 255, 255, 0.8); backdrop-filter: blur(20px); padding: 3rem; border-radius: 30px; }
    [data-testid="stFileUploaderDeleteBtn"], [data-testid="stFileUploaderFileName"] { display: none !important; }
    .stButton>button { border-radius: 12px; font-weight: 600; width: 100%; }
    </style>
    """, unsafe_allow_html=True)

st.title("Pugether Studio")
tabs = st.tabs(["🧩 批量拼图", "🔩 快速拆图"])

def 自然排序(text):
    return [int(c) if c.isdigit() else c.lower() for c in re.split('([0-9]+)', text)]

def auto_smart_split(img):
    """
    全自动内容识别拆分：
    不寻找分割线，而是寻找两个独立的内容实体。
    """
    # 转换成RGBA方便处理透明度和背景
    img = img.convert("RGBA")
    w, h = img.size
    
    # 1. 自动探测背景色 (取四个角)
    corners = [img.getpixel((0,0)), img.getpixel((w-1,0)), img.getpixel((0,h-1)), img.getpixel((w-1,h-1))]
    bg_color = max(set(corners), key=corners.count)
    
    # 2. 创建掩码：找出非背景区域
    bg = Image.new("RGBA", img.size, bg_color)
    diff = ImageChops.difference(img, bg)
    # 增强差异
    mask = diff.convert("L").point(lambda x: 255 if x > 10 else 0)
    bbox = mask.getbbox()
    
    if not bbox:
        return [img.crop((0,0,w//2,h)), img.crop((w//2,0,w,h))]

    # 3. 在中部区域寻找最细的“垂直空白带”作为切割点
    mask_arr = np.array(mask)
    # 计算每一列的像素密度
    col_density = np.sum(mask_arr, axis=0)
    
    # 扫描中部 30%-70% 区域，找到像素密度最小的列
    mid_start, mid_end = int(w * 0.3), int(w * 0.7)
    split_pos = mid_start + np.argmin(col_density[mid_start:mid_end])
    
    # 4. 拆分并自动修剪每一张图的白边
    part1 = img.crop((0, 0, split_pos, h))
    part2 = img.crop((split_pos, 0, w, h))
    
    def trim(im):
        # 再次精准去除子图白边
        bg_sub = Image.new("RGBA", im.size, bg_color)
        diff_sub = ImageChops.difference(im, bg_sub)
        bbox_sub = diff_sub.convert("L").point(lambda x: 255 if x > 10 else 0).getbbox()
        return im.crop(bbox_sub) if bbox_sub else im

    return [trim(part1), trim(part2)]

# --- 1. 拼图区 ---
with tabs[0]:
    h1, h2 = st.columns([0.8, 0.2])
    h1.markdown("### 1. 上传素材")
    if h2.button("🧹 一键清空", key="p_clr"):
        st.session_state.p_clear_id += 1
        st.rerun()

    up_p = st.file_uploader("图片", type=["png", "jpg", "jpeg"], accept_multiple_files=True, label_visibility="collapsed", key=f"p_u_{st.session_state.p_clear_id}")
    
    if up_p:
        st.info(f"已选中 {len(up_p)} 张图片")
        c1, c2 = st.columns(2)
        with c1: dir_mode = st.segmented_control("方向", ["左右", "上下"], default="左右")
        with c2: is_align = st.toggle("无痕拼图", value=False)

        if st.button("🚀 开始批量拼图", key="p_start_btn"):
            sorted_files = sorted(up_p, key=lambda x: 自然排序(x.name))
            total_pairs = len(sorted_files) // 2
            p_status = st.empty(); p_bar = st.progress(0); zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "a", zipfile.ZIP_DEFLATED) as zf:
                for i in range(0, total_pairs * 2, 2):
                    p_status.text(f"拼装中: {i//2+1} / {total_pairs}")
                    img1, img2 = Image.open(sorted_files[i]).convert("RGBA"), Image.open(sorted_files[i+1]).convert("RGBA")
                    if is_align:
                        th = max(img1.height, img2.height)
                        img1 = img1.resize((int(img1.width*th/img1.height), th), Image.Resampling.LANCZOS)
                        img2 = img2.resize((int(img2.width*th/img2.height), th), Image.Resampling.LANCZOS)
                    
                    w_c = img1.width + img2.width if dir_mode == "左右拼" else max(img1.width, img2.width)
                    h_c = max(img1.height, img2.height) if dir_mode == "左右拼" else img1.height + img2.height
                    canvas = Image.new('RGBA', (w_c, h_c), (255, 255, 255, 255))
                    canvas.paste(img1,(0,0)); canvas.paste(img2,(img1.width if dir_mode == "左右拼" else 0, 0 if dir_mode == "左右拼" else img1.height))
                    
                    tmp = io.BytesIO(); canvas.save(tmp, format="PNG")
                    zf.writestr(f"Result_{i//2+1}.png", tmp.getvalue())
                    p_bar.progress((i + 2) / (total_pairs * 2))
            st.balloons()
            st.download_button("📂 下载拼图包", zip_buf.getvalue(), "Export.zip")

# --- 2. 拆图区 (全自动版) ---
with tabs[1]:
    u1, u2 = st.columns([0.8, 0.2])
    u1.markdown("### 1. 上传拼图")
    if u2.button("🧹 一键清空", key="u_clr"):
        st.session_state.u_clear_id += 1
        st.rerun()

    up_u = st.file_uploader("图片", type=["png", "jpg"], accept_multiple_files=True, label_visibility="collapsed", key=f"u_u_{st.session_state.u_clear_id}")
    
    if up_u:
        if st.button("🔍 立即全自动拆分", key="u_start_btn"):
            u_status = st.empty(); u_bar = st.progress(0); zip_buf_u = io.BytesIO()
            total = len(up_u)
            with zipfile.ZipFile(zip_buf_u, "a", zipfile.ZIP_DEFLATED) as zf:
                for idx, f in enumerate(up_u):
                    u_status.text(f"自动分析并还原: {idx+1}/{total}")
                    img = Image.open(f)
                    
                    # 执行全自动智能拆分
                    results = auto_smart_split(img)
                    
                    for sub_idx, res in enumerate(results):
                        b = io.BytesIO()
                        res.save(b, "PNG")
                        suffix = "A" if sub_idx == 0 else "B"
                        zf.writestr(f"{f.name}_{suffix}.png", b.getvalue())
                    
                    u_bar.progress((idx + 1) / total)
            
            u_status.success(f"✨ 全自动还原完成")
            st.download_button("📂 下载还原包", zip_buf_u.getvalue(), "Restored.zip")
